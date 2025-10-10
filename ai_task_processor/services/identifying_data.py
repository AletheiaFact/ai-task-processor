from abc import ABC, abstractmethod
from typing import Dict, Any
from ..config import settings, ProcessingMode
from ..utils import get_logger, RetryableError, NonRetryableError
from .openai_client import openai_client
from .ollama_client import ollama_client

logger = get_logger(__name__)


class IdentifyingDataProvider(ABC):
    """Abstract base class for identifying data"""
    
    @abstractmethod
    async def create_identifying_data(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Create identifying data for the given text using the specified model"""
        pass
    
    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model"""
        pass


class OpenAIIdentifyingDataProvider(IdentifyingDataProvider):
    """OpenAI identifying data provider - flexible with any model from task metadata"""
    
    def supports_model(self, model: str) -> bool:
        # OpenAI is flexible - accept any model and let OpenAI API validate
        # This allows using new models without code changes
        return True
    
    async def create_identifying_data(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        # Check if using mock mode
        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock OpenAI identifying data (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            # Generate mock identifying data with personality detection
            import random
            dimensions = 1024
            mock_embedding = [random.uniform(-1, 1) for _ in range(dimensions)]
            
            # Mock personality detection for testing
            personalities = self._extract_personalities_mock(text)
            
            return {
                "personalities": personalities,
                "model": model,
                "usage": {
                    "prompt_tokens": len(text.split()),
                    "total_tokens": len(text.split())
                }
            }
        
        # Use OpenAI to identify personalities in the text
        personalities = await self._identify_personalities_with_openai(text, model, correlation_id)
        
        return {
            "personalities": personalities
        }
    
    def _extract_personalities_mock(self, text: str) -> list:
        """Mock personality extraction for testing purposes"""
        # Simple mock implementation that looks for common Brazilian political figures
        personalities = []
        text_lower = text.lower()
        
        # Common Brazilian political figures
        political_figures = {
            'lula': 'Luiz Inácio Lula da Silva',
            'bolsonaro': 'Jair Bolsonaro',
            'dilma': 'Dilma Rousseff',
            'temer': 'Michel Temer',
            'collor': 'Fernando Collor',
            'fhc': 'Fernando Henrique Cardoso',
            'marina': 'Marina Silva',
            'ciro': 'Ciro Gomes',
            'alckmin': 'Geraldo Alckmin'
        }
        
        for key, full_name in political_figures.items():
            if key in text_lower:
                personalities.append({
                    "name": full_name,
                    "mentioned_as": key,
                    "confidence": 0.9,
                    "context": text
                })
        
        return personalities
    
    async def _identify_personalities_with_openai(self, text: str, model: str, correlation_id: str = None) -> list:
        """Use OpenAI to identify personalities mentioned in the text"""
        prompt = f"""
        Analyze the following text and identify any personalities (people) mentioned in it. 
        Return the result as a JSON array with the following structure for each personality found:
        [
            {{
                "name": "Full name of the person",
                "mentioned_as": "How they are mentioned in the text",
                "confidence": 0.95,
                "context": "Brief context of how they are mentioned"
            }}
        ]
        
        Text to analyze: "{text}"
        
        If no personalities are found, return an empty array [].
        """
        
        try:
            response = await openai_client.create_completion(
                prompt=prompt,
                model=model,
                correlation_id=correlation_id
            )
            
            # Parse the JSON response
            import json
            personalities = json.loads(response.get('choices', [{}])[0].get('text', '[]'))
            return personalities
            
        except Exception as e:
            logger.error(
                "Failed to identify personalities with OpenAI",
                error=str(e),
                correlation_id=correlation_id
            )
            return []

class IdentifyingDataFactory:
    """Factory for creating appropriate identifying data"""
    
    @staticmethod
    def create_provider() -> IdentifyingDataProvider:
        if settings.processing_mode == ProcessingMode.OPENAI:
            logger.info("Using OpenAI identifying data provider")
            return OpenAIIdentifyingDataProvider()
        else:
            logger.warning(f"Unknown processing mode: {settings.processing_mode}, defaulting to OpenAI")
            return OpenAIIdentifyingDataProvider()


# Global provider instance
identifying_data = IdentifyingDataFactory.create_provider()