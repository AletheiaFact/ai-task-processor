"""Fallback from Jev to OpenAI for impact area and severity, with a daily cap.

Why the fallback is limited (see also the Jev fallback settings in config/settings.py):
- Jev is the main provider because it is much cheaper. An unlimited fallback would hide
  a broken Jev behind o3 calls, and the cost would grow before anyone noticed.
- Without any fallback, a failed task stays FAILED and the VR stays in "Pre Triage":
  the backend does not retry stale AI tasks yet (checkAndRetryStaleAiTasks is not scheduled).

So only temporary errors fall back, at most JEV_FALLBACK_MAX_PER_DAY times per day (UTC),
and every outcome is counted in the triage_provider_total metric.

TODO (tech debt): add a circuit breaker for Jev. Today, while Jev is down, every task
still goes through all the Jev retries (up to ~2 min 15 s with JEV_BACKOFF_SECONDS)
before falling back or failing. Cost stays capped, but triage slows down during an outage.
An open breaker would skip Jev right away (like the circuit breaker in api_client.py).
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

import aiosqlite

from ..config import settings
from ..utils import get_logger, RetryableError, NonRetryableError
from .jev_client import is_jev_model
from .metrics import metrics

logger = get_logger(__name__)


class JevFallbackBudget:
    """Daily count of OpenAI fallbacks, persisted in SQLite so restarts do not reset it."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.rate_limit_storage_path
        self._lock = asyncio.Lock()

    async def try_reserve(self, max_per_day: int) -> bool:
        """Count one fallback for today if the cap allows it."""
        if max_per_day <= 0:
            return False

        today = datetime.now(timezone.utc).date().isoformat()
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS jev_fallbacks (day TEXT PRIMARY KEY, count INTEGER NOT NULL)"
                )
                await db.execute("INSERT OR IGNORE INTO jev_fallbacks (day, count) VALUES (?, 0)", (today,))
                cursor = await db.execute(
                    "UPDATE jev_fallbacks SET count = count + 1 WHERE day = ? AND count < ?",
                    (today, max_per_day)
                )
                await db.commit()
                return cursor.rowcount == 1
        except Exception as e:
            # Fail closed: without the counter, the cost cannot be bounded
            logger.error("Jev fallback counter unavailable, not falling back", error=str(e))
            return False

    async def used_today(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT count FROM jev_fallbacks WHERE day = ?", (today,))
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0


jev_fallback_budget = JevFallbackBudget()


async def with_openai_fallback(
    task_type: str,
    jev_call: Callable[[], Awaitable[Dict[str, Any]]],
    openai_call: Callable[[str], Awaitable[Dict[str, Any]]],
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Run the Jev call; on a temporary error, run the OpenAI call with JEV_FALLBACK_MODEL
    if today's cap allows it.

    Args:
        task_type: "defining_impact_area" or "defining_severity", for logs and metrics
        jev_call: the Jev path, already retried inside the Jev client
        openai_call: the current OpenAI path, called with the fallback model
    """
    try:
        result = await jev_call()
        metrics.record_triage_provider(task_type, "jev")
        return result

    except NonRetryableError:
        # Jev is broken (key, access, request), not overloaded: fail loud, no o3 cost
        metrics.record_triage_provider(task_type, "jev_error")
        raise

    except RetryableError as e:
        max_per_day = settings.jev_fallback_max_per_day
        if not await jev_fallback_budget.try_reserve(max_per_day):
            logger.error(
                "Jev failed and the OpenAI fallback is disabled or over its daily limit",
                task_type=task_type,
                error=str(e),
                max_per_day=max_per_day,
                correlation_id=correlation_id
            )
            metrics.record_triage_provider(task_type, "fallback_limit_reached")
            raise RetryableError(f"Jev unavailable and OpenAI fallback limit reached ({max_per_day}/day): {e}")

        fallback_model = settings.jev_fallback_model
        if is_jev_model(fallback_model):
            # Would route back to Jev in a loop
            raise NonRetryableError(f"JEV_FALLBACK_MODEL must be an OpenAI model, got '{fallback_model}'")

        logger.warning(
            "Jev failed, falling back to OpenAI",
            task_type=task_type,
            fallback_model=fallback_model,
            error=str(e),
            correlation_id=correlation_id
        )
        metrics.record_triage_provider(task_type, "openai_fallback")
        return await openai_call(fallback_model)
