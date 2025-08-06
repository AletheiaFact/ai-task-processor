import asyncio
import random
from typing import Any, Callable, Type, Tuple, Optional
from functools import wraps
from ..config import settings
from .logger import get_logger

logger = get_logger(__name__)


class RetryableError(Exception):
    pass


class NonRetryableError(Exception):
    pass


async def exponential_backoff_retry(
    func: Callable,
    max_retries: int = None,
    backoff_factor: float = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (NonRetryableError,),
    jitter: bool = True,
    correlation_id: Optional[str] = None
) -> Any:
    max_retries = max_retries or settings.max_retries
    backoff_factor = backoff_factor or settings.retry_backoff_factor
    
    for attempt in range(max_retries + 1):
        try:
            result = await func()
            if attempt > 0:
                logger.info(
                    "Function succeeded after retry",
                    attempt=attempt,
                    correlation_id=correlation_id
                )
            return result
        except non_retryable_exceptions as e:
            logger.error(
                "Non-retryable error occurred",
                error=str(e),
                correlation_id=correlation_id
            )
            raise
        except retryable_exceptions as e:
            if attempt == max_retries:
                logger.error(
                    "Max retries exceeded",
                    error=str(e),
                    attempts=attempt + 1,
                    correlation_id=correlation_id
                )
                raise
            
            delay = backoff_factor ** attempt
            if jitter:
                delay += random.uniform(0, delay * 0.1)
            
            logger.warning(
                "Retrying after error",
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
                correlation_id=correlation_id
            )
            
            await asyncio.sleep(delay)


def retry(
    max_retries: int = None,
    backoff_factor: float = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (NonRetryableError,)
):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async def inner():
                return await func(*args, **kwargs)
            
            return await exponential_backoff_retry(
                inner,
                max_retries=max_retries,
                backoff_factor=backoff_factor,
                retryable_exceptions=retryable_exceptions,
                non_retryable_exceptions=non_retryable_exceptions
            )
        return wrapper
    return decorator