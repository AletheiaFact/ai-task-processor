import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from ..config import settings
from ..utils import get_logger, retry, RetryableError, NonRetryableError
from .metrics import metrics

logger = get_logger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=settings.ollama_timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _check_model_exists(self, model: str, correlation_id: str = None) -> bool:
        """Check if model exists locally, if not trigger download"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get('name', '').split(':')[0] for m in data.get('models', [])]
                    return model in models or f"{model}:latest" in [m.get('name', '') for m in data.get('models', [])]
                return False
        except Exception as e:
            logger.warning(
                "Failed to check model existence",
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            return False
    
    async def _download_model(self, model: str, correlation_id: str = None):
        """Download model if it doesn't exist"""
        try:
            logger.info(
                "Downloading Ollama model",
                model=model,
                correlation_id=correlation_id
            )
            
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=settings.ollama_model_download_timeout)
            
            async with session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
                timeout=timeout
            ) as response:
                if response.status == 200:
                    # Stream the download progress
                    async for line in response.content:
                        try:
                            # Parse JSON response line by line (Ollama streams JSON)
                            data = await response.json() if hasattr(response, 'json') else None
                            if data and data.get('status'):
                                logger.info(
                                    "Model download progress",
                                    model=model,
                                    status=data.get('status'),
                                    correlation_id=correlation_id
                                )
                        except:
                            # Skip malformed JSON lines
                            continue
                    
                    logger.info(
                        "Model downloaded successfully",
                        model=model,
                        correlation_id=correlation_id
                    )
                else:
                    raise RetryableError(f"Failed to download model {model}: HTTP {response.status}")
                    
        except asyncio.TimeoutError:
            raise RetryableError(f"Model download timeout for {model}")
        except Exception as e:
            logger.error(
                "Model download failed",
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            raise RetryableError(f"Model download failed: {e}")
    
    @retry(
        retryable_exceptions=(
            aiohttp.ClientTimeout,
            aiohttp.ClientConnectionError,
            aiohttp.ServerTimeoutError,
            RetryableError
        ),
        non_retryable_exceptions=(
            aiohttp.ClientResponseError,
            NonRetryableError
        )
    )
    async def create_embedding(
        self, 
        text: str, 
        model: str = "nomic-embed-text",
        correlation_id: str = None
    ) -> Dict[str, Any]:
        try:
            logger.info(
                "Creating Ollama embedding",
                model=model,
                text_length=len(text),
                correlation_id=correlation_id
            )
            
            # Check if model exists, download if needed
            if not await self._check_model_exists(model, correlation_id):
                await self._download_model(model, correlation_id)
            
            session = await self._get_session()
            
            payload = {
                "model": model,
                "prompt": text
            }
            
            async with session.post(
                f"{self.base_url}/api/embeddings",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    embedding = data.get("embedding", [])
                    
                    if not embedding:
                        raise NonRetryableError("Empty embedding received from Ollama")
                    
                    # Ollama doesn't provide token usage, estimate it
                    estimated_tokens = len(text.split())
                    usage = {
                        "prompt_tokens": estimated_tokens,
                        "total_tokens": estimated_tokens
                    }
                    
                    metrics.record_ollama_request(model, "success", usage)
                    
                    logger.info(
                        "Ollama embedding created successfully",
                        model=model,
                        embedding_dimensions=len(embedding),
                        estimated_tokens=estimated_tokens,
                        correlation_id=correlation_id
                    )
                    
                    return {
                        "embedding": embedding,
                        "model": model,
                        "usage": usage
                    }
                
                elif response.status == 404:
                    error_text = await response.text()
                    logger.error(
                        "Ollama model not found",
                        model=model,
                        error=error_text,
                        correlation_id=correlation_id
                    )
                    metrics.record_ollama_request(model, "model_not_found")
                    raise NonRetryableError(f"Model {model} not found: {error_text}")
                
                elif response.status >= 500:
                    error_text = await response.text()
                    logger.warning(
                        "Ollama server error",
                        status=response.status,
                        error=error_text,
                        correlation_id=correlation_id
                    )
                    metrics.record_ollama_request(model, "server_error")
                    raise RetryableError(f"Ollama server error {response.status}: {error_text}")
                
                else:
                    error_text = await response.text()
                    logger.error(
                        "Ollama client error",
                        status=response.status,
                        error=error_text,
                        correlation_id=correlation_id
                    )
                    metrics.record_ollama_request(model, "client_error")
                    raise NonRetryableError(f"Ollama client error {response.status}: {error_text}")
                    
        except aiohttp.ClientTimeout as e:
            logger.warning(
                "Ollama request timeout",
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_ollama_request(model, "timeout")
            raise RetryableError(f"Ollama timeout: {e}")
            
        except aiohttp.ClientConnectionError as e:
            logger.warning(
                "Ollama connection error",
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_ollama_request(model, "connection_error")
            raise RetryableError(f"Ollama connection error: {e}")
            
        except Exception as e:
            logger.error(
                "Unexpected Ollama error",
                model=model,
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_ollama_request(model, "unknown_error")
            raise NonRetryableError(f"Unexpected Ollama error: {e}")


ollama_client = OllamaClient()