"""
Generic AI Provider abstraction that supports multiple processing modes (OpenAI, Ollama, Hybrid)
for all AI task types, not just embeddings.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..config import settings, ProcessingMode
from ..utils import get_logger, RetryableError, NonRetryableError
from .openai_client import openai_client
from .ollama_client import ollama_client

logger = get_logger(__name__)


class AIProvider(ABC):
    """Abstract base class for AI providers that support multiple operation types"""

    @abstractmethod
    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Create embedding for the given text using the specified model"""
        pass

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate chat completion for the given messages"""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text completion for the given prompt"""
        pass

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model"""
        pass


class OpenAIProvider(AIProvider):
    """OpenAI provider - flexible with any model from task metadata"""

    def supports_model(self, model: str) -> bool:
        # OpenAI is flexible - accept any model and let OpenAI API validate
        # This allows using new models without code changes
        return True

    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Create embedding using OpenAI"""
        # Check if API key is not configured or is placeholder
        if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock OpenAI embedding data (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            # Generate mock embedding vector with 1024 dimensions
            import random
            dimensions = 1024
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

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate chat completion using OpenAI"""
        # Check if API key is not configured or is placeholder
        if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock OpenAI chat completion (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            # Generate mock response
            return {
                "content": "Mock response: This is a simulated AI response for testing purposes.",
                "model": model,
                "usage": {
                    "prompt_tokens": sum(len(m.get("content", "").split()) for m in messages),
                    "completion_tokens": 10,
                    "total_tokens": sum(len(m.get("content", "").split()) for m in messages) + 10
                }
            }

        return await openai_client.chat_completion(
            messages=messages,
            model=model,
            correlation_id=correlation_id,
            **kwargs
        )

    async def generate(
        self,
        prompt: str,
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text completion using OpenAI (wraps chat_completion)"""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(
            messages=messages,
            model=model,
            correlation_id=correlation_id,
            **kwargs
        )


class OllamaProvider(AIProvider):
    """Ollama provider - only supports models defined in configuration"""

    def supports_model(self, model: str) -> bool:
        # Only support models explicitly configured in SUPPORTED_MODELS
        # These are the models that will be installed/available locally
        return model in settings.supported_models

    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Create embedding using Ollama"""
        return await ollama_client.create_embedding(
            text=text,
            model=model,
            correlation_id=correlation_id
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate chat completion using Ollama"""
        # Convert messages to prompt format for Ollama
        prompt = self._messages_to_prompt(messages)
        return await self.generate(prompt, model, correlation_id, **kwargs)

    async def generate(
        self,
        prompt: str,
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text completion using Ollama"""
        return await ollama_client.generate(
            prompt=prompt,
            model=model,
            correlation_id=correlation_id,
            **kwargs
        )

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI message format to simple prompt"""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        return "\n".join(prompt_parts)


class HybridProvider(AIProvider):
    """Hybrid provider that tries Ollama first, falls back to OpenAI"""

    def __init__(self):
        self.ollama_provider = OllamaProvider()
        self.openai_provider = OpenAIProvider()

    def supports_model(self, model: str) -> bool:
        return self.ollama_provider.supports_model(model) or self.openai_provider.supports_model(model)

    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Try Ollama first for embeddings, fallback to OpenAI"""
        return await self._execute_with_fallback(
            operation="create_embedding",
            ollama_supports=self.ollama_provider.supports_model(model),
            text=text,
            model=model,
            correlation_id=correlation_id
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Try Ollama first for chat completion, fallback to OpenAI"""
        return await self._execute_with_fallback(
            operation="chat_completion",
            ollama_supports=self.ollama_provider.supports_model(model),
            messages=messages,
            model=model,
            correlation_id=correlation_id,
            **kwargs
        )

    async def generate(
        self,
        prompt: str,
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Try Ollama first for generation, fallback to OpenAI"""
        return await self._execute_with_fallback(
            operation="generate",
            ollama_supports=self.ollama_provider.supports_model(model),
            prompt=prompt,
            model=model,
            correlation_id=correlation_id,
            **kwargs
        )

    async def _execute_with_fallback(
        self,
        operation: str,
        ollama_supports: bool,
        model: str,
        correlation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute operation with Ollama first, OpenAI fallback"""

        # First try Ollama if it supports the model
        if ollama_supports:
            try:
                logger.info(
                    f"Attempting Ollama {operation} (hybrid mode)",
                    model=model,
                    correlation_id=correlation_id
                )

                # Call the appropriate method on ollama_provider
                method = getattr(self.ollama_provider, operation)
                return await method(model=model, correlation_id=correlation_id, **kwargs)

            except Exception as e:
                logger.warning(
                    f"Ollama {operation} failed in hybrid mode, falling back to OpenAI",
                    model=model,
                    error=str(e),
                    correlation_id=correlation_id
                )

        # Fallback to OpenAI if Ollama fails or doesn't support the model
        if self.openai_provider.supports_model(model):
            logger.info(
                f"Using OpenAI {operation} fallback in hybrid mode",
                model=model,
                correlation_id=correlation_id
            )

            # Call the appropriate method on openai_provider
            method = getattr(self.openai_provider, operation)
            return await method(model=model, correlation_id=correlation_id, **kwargs)

        # If neither provider supports the model, raise an error
        raise NonRetryableError(f"No provider supports model: {model}")


class AIProviderFactory:
    """Factory for creating appropriate AI providers based on processing mode"""

    @staticmethod
    def create_provider() -> AIProvider:
        if settings.processing_mode == ProcessingMode.OPENAI:
            logger.info("Using OpenAI AI provider")
            return OpenAIProvider()
        elif settings.processing_mode == ProcessingMode.OLLAMA:
            logger.info("Using Ollama AI provider")
            return OllamaProvider()
        elif settings.processing_mode == ProcessingMode.HYBRID:
            logger.info("Using Hybrid AI provider")
            return HybridProvider()
        else:
            logger.warning(f"Unknown processing mode: {settings.processing_mode}, defaulting to OpenAI")
            return OpenAIProvider()


# Global provider instance
ai_provider = AIProviderFactory.create_provider()
