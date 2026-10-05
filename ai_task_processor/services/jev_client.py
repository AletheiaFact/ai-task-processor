"""Client for Jev, TypeSafe's evaluation model, through the TypeSafe API.

Callers use "boolean" for yes/no questions, which TypeSafe calls "noul". Answers are
normalized so callers never depend on the wire format.

With the placeholder API key (same rule as OpenAI), the client returns mock answers in
the same format, so everything after Jev (matrices, severity bands, callbacks) runs for
real at zero cost. A missing key is an error, so production never stores mock results.
"""
import asyncio
import hashlib
import json
import random
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings
from ..utils import get_logger, RetryableError, NonRetryableError
from .metrics import metrics

logger = get_logger(__name__)

TYPESAFE_BASE_URL = "https://api.typesafe.ai"
TYPESAFE_API_KEY_PLACEHOLDER = "your_typesafe_api_key_here"
MOCK_MODEL = "jev-mock"

# Overload, rate limiting and upstream hiccups are worth waiting out
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_jev_model(model: Optional[str]) -> bool:
    """Tasks are routed to Jev when the backend sends a Jev model (e.g. "jev-1.13.0")."""
    return bool(model) and model.lower().startswith("jev")


class JevClient:
    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        # Tests inject an httpx.MockTransport so no real request is made
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_mock(self) -> bool:
        return settings.typesafe_api_key == TYPESAFE_API_KEY_PLACEHOLDER

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=settings.jev_timeout,
                transport=self._transport
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def evaluate(
        self,
        state: Any,
        questions: Dict[str, Dict[str, Any]],
        model: str,
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """
        Ask Jev the given questions about the state.

        Args:
            state: Text or JSON object to evaluate
            questions: Questions keyed by name, each one of:
                {"type": "score", "instructions": str, "criteria": [level0, level1, ...]}
                {"type": "boolean", "instructions": str}
                {"type": "choice", "instructions": str, "criteria": {option: description | None}}
            model: Jev model id (e.g. "jev-1.13.0")
            correlation_id: Correlation ID for tracking

        Returns:
            {
                "answers": {name: answer},
                "usage": {"input_tokens": int | None, "output_tokens": int | None},
                "model": str  # "jev-mock" for mock answers
            }
            where each answer is one of:
                {"type": "score", "score": float, "probabilities": [p0, p1, ...], "confidence": float | None}
                {"type": "boolean", "probability": float}
                {"type": "choice", "choice": str, "probabilities": {option: p}, "confidence": float | None}
        """
        if self.is_mock:
            # Loud on purpose: a placeholder key in production must not go unnoticed
            logger.warning(
                "Using mock Jev answers (placeholder TypeSafe API key)",
                model=model,
                questions=list(questions),
                correlation_id=correlation_id
            )
            metrics.record_jev_request(model, "mock")
            return self._mock_response(state, questions)

        if not settings.typesafe_api_key:
            raise NonRetryableError("TypeSafe API key is not configured")

        url, headers, body = self._build_request(state, questions, model)
        backoff = settings.jev_backoff_seconds

        for attempt in range(len(backoff) + 1):
            try:
                logger.info(
                    "Calling Jev",
                    model=model,
                    questions=list(questions),
                    attempt=attempt + 1,
                    correlation_id=correlation_id
                )
                data = await self._post(url, headers, body)
                result = self._parse_response(data, questions, model)
                metrics.record_jev_request(model, "success", result["usage"])
                return result

            except RetryableError as e:
                if attempt >= len(backoff):
                    logger.error(
                        "Jev retries exhausted",
                        error=str(e),
                        attempts=attempt + 1,
                        correlation_id=correlation_id
                    )
                    metrics.record_jev_request(model, "retries_exhausted")
                    raise
                delay = backoff[attempt] * (0.8 + random.random() * 0.4)
                logger.warning(
                    "Jev temporary error, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    delay=round(delay, 1),
                    correlation_id=correlation_id
                )
                metrics.record_jev_request(model, "retry")
                await asyncio.sleep(delay)

            except NonRetryableError as e:
                logger.error(
                    "Jev request failed",
                    error=str(e),
                    correlation_id=correlation_id
                )
                metrics.record_jev_request(model, "error")
                raise

    def _build_request(self, state: Any, questions: Dict[str, Dict[str, Any]], model: str):
        base_url = (settings.jev_base_url or TYPESAFE_BASE_URL).rstrip("/")
        headers = {"Authorization": f"Bearer {settings.typesafe_api_key}"}
        wire_questions = {
            name: {**question, "type": "noul"} if question["type"] == "boolean" else question
            for name, question in questions.items()
        }
        body = {"state": state, "model": model, "questions": wire_questions}
        return f"{base_url}/v1/systemone", headers, body

    async def _post(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._get_client()
        try:
            response = await client.post(url, headers=headers, json=body)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise RetryableError(f"Jev connection error: {type(e).__name__}: {e}")

        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableError(f"Jev HTTP {response.status_code}: {response.text[:300]}")
        if response.status_code >= 400:
            raise NonRetryableError(f"Jev HTTP {response.status_code}: {response.text[:300]}")

        try:
            return response.json()
        except ValueError:
            raise NonRetryableError("Jev returned a response that is not JSON")

    def _parse_response(
        self,
        data: Dict[str, Any],
        questions: Dict[str, Dict[str, Any]],
        model: str
    ) -> Dict[str, Any]:
        raw_answers = data.get("answers") or {}
        missing = [name for name in questions if name not in raw_answers]
        if missing:
            raise NonRetryableError(f"Jev response is missing answers for: {missing}")

        answers = {}
        for name, question in questions.items():
            raw = raw_answers[name]

            if question["type"] == "score":
                answers[name] = {
                    "type": "score",
                    "score": float(raw["score"]),
                    "probabilities": self._ordered_probabilities(
                        name, raw.get("probabilities"), len(question["criteria"])
                    ),
                    "confidence": raw.get("confidence"),
                }
            elif question["type"] == "boolean":
                if raw.get("noul") is None:
                    raise NonRetryableError(f"Jev boolean answer '{name}' has no probability")
                answers[name] = {"type": "boolean", "probability": float(raw["noul"])}
            elif question["type"] == "choice":
                answers[name] = {
                    "type": "choice",
                    "choice": raw["choice"],
                    "probabilities": raw.get("probabilities") or {},
                    "confidence": raw.get("confidence"),
                }
            else:
                raise NonRetryableError(f"Unsupported Jev question type: {question['type']}")

        usage = data.get("usage") or {}
        return {
            "answers": answers,
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
            "model": data.get("model", model),
        }

    @staticmethod
    def _ordered_probabilities(name: str, probabilities: Optional[Dict[str, float]], levels: int) -> List[float]:
        """Score probabilities in rubric order, from keys "0", "1", ..."""
        probabilities = probabilities or {}
        try:
            ordered = [float(probabilities[str(i)]) for i in range(levels)]
        except KeyError:
            raise NonRetryableError(
                f"Jev score answer '{name}' expected {levels} levels, got {sorted(probabilities)}"
            )
        return ordered

    def _mock_response(self, state: Any, questions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Mock answers for testing without an API key.

        Seeded by the state and the question name: the same text always gets the
        same answers, and different texts land on different levels.
        """
        state_key = json.dumps(state, sort_keys=True, ensure_ascii=False)
        answers = {}
        for name, question in questions.items():
            seed = hashlib.sha256(f"{name}:{state_key}".encode("utf-8")).hexdigest()
            rng = random.Random(seed)

            if question["type"] == "score":
                probabilities = self._mock_distribution(rng, len(question["criteria"]))
                answers[name] = {
                    "type": "score",
                    "score": sum(i * p for i, p in enumerate(probabilities)),
                    "probabilities": probabilities,
                    "confidence": self._confidence(probabilities),
                }
            elif question["type"] == "boolean":
                answers[name] = {"type": "boolean", "probability": rng.random()}
            elif question["type"] == "choice":
                options = list(question["criteria"])
                probabilities = self._mock_distribution(rng, len(options))
                answers[name] = {
                    "type": "choice",
                    "choice": options[probabilities.index(max(probabilities))],
                    "probabilities": dict(zip(options, probabilities)),
                    "confidence": self._confidence(probabilities),
                }
            else:
                raise NonRetryableError(f"Unsupported Jev question type: {question['type']}")

        return {
            "answers": answers,
            "usage": {"input_tokens": None, "output_tokens": None},
            "model": MOCK_MODEL,
        }

    @staticmethod
    def _mock_distribution(rng: random.Random, size: int) -> List[float]:
        """A distribution with one clear peak, like Jev usually returns."""
        peak = rng.randrange(size)
        weights = [3.0 if i == peak else rng.uniform(0.05, 0.6) for i in range(size)]
        return [w / sum(weights) for w in weights]

    @staticmethod
    def _confidence(probabilities: List[float]) -> float:
        """TypeSafe's definition: (count * peak - 1) / (count - 1)."""
        count = len(probabilities)
        if count < 2:
            return 1.0
        return (count * max(probabilities) - 1) / (count - 1)


jev_client = JevClient()
