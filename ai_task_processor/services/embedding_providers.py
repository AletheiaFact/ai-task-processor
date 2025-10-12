"""
DEPRECATED: This module is kept for backward compatibility.
Use ai_provider.py for generic AI operations across all task types.

This module provides a compatibility wrapper that delegates to the new generic AIProvider.
"""

from typing import Dict, Any
from ..utils import get_logger

# Import the new generic provider
from .ai_provider import ai_provider

logger = get_logger(__name__)

logger.warning(
    "embedding_providers.py is deprecated. Use ai_provider.py instead for all AI operations."
)


class EmbeddingProvider:
    """
    Backward compatibility wrapper for embedding operations.
    Delegates to the generic AIProvider.
    """

    def __init__(self, wrapped_provider):
        self._provider = wrapped_provider

    async def create_embedding(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Create embedding - delegates to generic AI provider"""
        return await self._provider.create_embedding(text, model, correlation_id)

    def supports_model(self, model: str) -> bool:
        """Check if provider supports model - delegates to generic AI provider"""
        return self._provider.supports_model(model)


# Global provider instance - wraps the generic ai_provider for backward compatibility
embedding_provider = EmbeddingProvider(ai_provider)