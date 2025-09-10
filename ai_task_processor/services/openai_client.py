import openai
from typing import List, Dict, Any
from ..config import settings
from ..utils import get_logger, retry, RetryableError, NonRetryableError
from .metrics import metrics

logger = get_logger(__name__)


class OpenAIClient:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout
        )
    
    @retry(
        retryable_exceptions=(
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.APIConnectionError
        ),
        non_retryable_exceptions=(
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.BadRequestError,
            NonRetryableError
        )
    )
    async def create_embedding(
        self, 
        text: str, 
        model: str = "text-embedding-3-small",
        correlation_id: str = None
    ) -> Dict[str, Any]:
        try:
            logger.info(
                "Creating embedding",
                model=model,
                text_length=len(text),
                correlation_id=correlation_id
            )
            
            response = await self.client.embeddings.create(
                model=model,
                input=text,
                dimensions=1024
            )
            
            embedding = response.data[0].embedding
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            metrics.record_openai_request(model, "success", usage)
            
            logger.info(
                "Embedding created successfully",
                model=model,
                embedding_dimensions=len(embedding),
                usage=usage,
                correlation_id=correlation_id
            )
            
            return {
                "embedding": embedding,
                "model": model,
                "usage": usage
            }
            
        except openai.RateLimitError as e:
            logger.warning(
                "OpenAI rate limit exceeded",
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_openai_request(model, "rate_limited")
            raise RetryableError(f"Rate limit exceeded: {e}")
            
        except (openai.APITimeoutError, openai.InternalServerError, openai.APIConnectionError) as e:
            logger.warning(
                "OpenAI temporary error",
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_openai_request(model, "error")
            raise RetryableError(f"Temporary OpenAI error: {e}")
            
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            logger.error(
                "OpenAI authentication error",
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_openai_request(model, "auth_error")
            raise NonRetryableError(f"Authentication error: {e}")
            
        except openai.BadRequestError as e:
            logger.error(
                "OpenAI bad request",
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_openai_request(model, "bad_request")
            raise NonRetryableError(f"Bad request: {e}")
            
        except Exception as e:
            logger.error(
                "Unexpected OpenAI error",
                error=str(e),
                correlation_id=correlation_id
            )
            metrics.record_openai_request(model, "unknown_error")
            raise NonRetryableError(f"Unexpected error: {e}")


openai_client = OpenAIClient()