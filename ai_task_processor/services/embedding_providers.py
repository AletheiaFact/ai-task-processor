from abc import ABC, abstractmethod
from typing import Dict, Any
from ..config import settings, ProcessingMode
from ..utils import get_logger, RetryableError, NonRetryableError
from .openai_client import openai_client
from .ollama_client import ollama_client

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""
    
    @abstractmethod
    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Create embedding for the given text using the specified model"""
        pass
    
    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model"""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""
    
    SUPPORTED_MODELS = {
        "text-embedding-3-small",
        "text-embedding-3-large", 
        "text-embedding-ada-002"
    }
    
    def supports_model(self, model: str) -> bool:
        return model in self.SUPPORTED_MODELS
    
    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        if not self.supports_model(model):
            raise NonRetryableError(f"OpenAI provider does not support model: {model}")
        
        # Check if using mock mode
        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock OpenAI embedding data (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            # Generate mock embedding vector
            import random
            dimensions = 1536 if "3-small" in model else 3072 if "3-large" in model else 1536
            mock_embedding = [random.uniform(-1, 1) for _ in range(dimensions)]
            return {
                "embedding": mock_embedding,
                "model": model,
                "usage": {
                    "prompt_tokens": len(text.split()),
                    "total_tokens": len(text.split())
                }
            }
        
        return await openai_client.create_embedding(
            text=text,
            model=model,
            correlation_id=correlation_id
        )


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama embedding provider for local models"""
    
    SUPPORTED_MODELS = {
        "nomic-embed-text",
        "all-minilm",
        "mxbai-embed-large",
        "snowflake-arctic-embed",
        "bge-large",
        "bge-base"
    }
    
    def supports_model(self, model: str) -> bool:
        # Ollama is flexible with models, but we maintain a list of known good models
        # Also support any model that the user might want to use
        return model in self.SUPPORTED_MODELS or True  # Allow any model for flexibility
    
    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        return await ollama_client.create_embedding(
            text=text,
            model=model,
            correlation_id=correlation_id
        )


class HybridEmbeddingProvider(EmbeddingProvider):
    """Hybrid provider that tries Ollama first, falls back to OpenAI"""
    
    def __init__(self):
        self.ollama_provider = OllamaEmbeddingProvider()
        self.openai_provider = OpenAIEmbeddingProvider()
    
    def supports_model(self, model: str) -> bool:
        return self.ollama_provider.supports_model(model) or self.openai_provider.supports_model(model)
    
    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        # First try Ollama if it supports the model
        if self.ollama_provider.supports_model(model):
            try:
                logger.info(
                    "Attempting Ollama embedding (hybrid mode)",
                    model=model,
                    correlation_id=correlation_id
                )
                return await self.ollama_provider.create_embedding(text, model, correlation_id)
            except Exception as e:
                logger.warning(
                    "Ollama failed in hybrid mode, falling back to OpenAI",
                    model=model,
                    error=str(e),
                    correlation_id=correlation_id
                )
        
        # Fallback to OpenAI if Ollama fails or doesn't support the model
        if self.openai_provider.supports_model(model):
            logger.info(
                "Using OpenAI fallback in hybrid mode",
                model=model,
                correlation_id=correlation_id
            )
            return await self.openai_provider.create_embedding(text, model, correlation_id)
        
        # If neither provider supports the model, raise an error
        raise NonRetryableError(f"No provider supports model: {model}")


class EmbeddingProviderFactory:
    """Factory for creating appropriate embedding providers"""
    
    @staticmethod
    def create_provider() -> EmbeddingProvider:
        if settings.processing_mode == ProcessingMode.OPENAI:
            logger.info("Using OpenAI embedding provider")
            return OpenAIEmbeddingProvider()
        elif settings.processing_mode == ProcessingMode.OLLAMA:
            logger.info("Using Ollama embedding provider")
            return OllamaEmbeddingProvider()
        elif settings.processing_mode == ProcessingMode.HYBRID:
            logger.info("Using Hybrid embedding provider")
            return HybridEmbeddingProvider()
        else:
            logger.warning(f"Unknown processing mode: {settings.processing_mode}, defaulting to OpenAI")
            return OpenAIEmbeddingProvider()


# Global provider instance
embedding_provider = EmbeddingProviderFactory.create_provider()