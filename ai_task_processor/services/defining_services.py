from abc import ABC, abstractmethod
from typing import Dict, Any, List
from ..config import settings
from ..utils import get_logger, RetryableError, NonRetryableError
from .openai_client import openai_client

logger = get_logger(__name__)


class DefiningTopicsProvider:
    """OpenAI provider for defining topics in text"""

    def supports_model(self, model: str) -> bool:
        # OpenAI is flexible - accept any model
        return True

    async def define_topics(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Define topics from the given text using OpenAI"""

        # Check if using mock mode
        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock topic definition (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            return self._mock_topics(text)

        # Use OpenAI to identify topics
        topics = await self._identify_topics_with_openai(text, model, correlation_id)

        return {
            "topics": topics,
            "model": model,
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    def _mock_topics(self, text: str) -> Dict[str, Any]:
        """Mock topic identification for testing"""
        mock_topics = [
            {
                "name": "Politics",
                "confidence": 0.95,
                "context": "The text discusses political matters"
            },
            {
                "name": "Economy",
                "confidence": 0.85,
                "context": "Economic issues are mentioned"
            }
        ]

        return {
            "topics": mock_topics,
            "model": "mock",
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    # TODO: at place using a text to identify the topics
    # we need request the wikidata to fetch possible topics related with personality
    # then we need abstract the VR context informations to identify the topics also
    async def _identify_topics_with_openai(self, text: str, model: str, correlation_id: str = None) -> List[Dict[str, Any]]:
        """Use OpenAI to identify topics in the text"""
        prompt = f"""
        Analyze the following text and identify the main topics discussed.
        Return the result as a JSON array with the following structure for each topic found:
        [
            {{
                "name": "Topic name",
                "confidence": 0.95,
                "context": "Brief context of the topic in the text"
            }}
        ]

        First try to access the url's and find possible topics from the page. If the url is not found, use the text to identify the topics.
        Url to access: {url}

        Text to analyze: "{text}"

        If no clear topics are found, return an empty array [].
        Only return the JSON array, no additional text.
        """

        try:
            response = await openai_client.create_completion(
                prompt=prompt,
                model=model,
                correlation_id=correlation_id
            )

            # Parse the JSON response
            import json
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '[]')
            topics = json.loads(content)

            print(f'topics: {topics}')
            return topics

        except Exception as e:
            logger.error(
                "Failed to identify topics with OpenAI",
                error=str(e),
                correlation_id=correlation_id
            )
            return []


class DefiningImpactAreaProvider:
    """OpenAI provider for defining impact areas"""

    def supports_model(self, model: str) -> bool:
        return True

    async def define_impact_areas(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Define impact areas from the given text using OpenAI"""

        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock impact area definition (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            return self._mock_impact_areas(text)

        impact_areas = await self._identify_impact_areas_with_openai(text, model, correlation_id)

        return {
            "impact_areas": impact_areas,
            "model": model,
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    def _mock_impact_areas(self, text: str) -> Dict[str, Any]:
        """Mock impact area identification for testing"""
        mock_impact_areas = [
            {
                "name": "Social Impact",
                "description": "Affects social structures and relationships",
                "confidence": 0.90
            },
            {
                "name": "Economic Impact",
                "description": "Influences economic conditions and markets",
                "confidence": 0.85
            }
        ]

        return {
            "impact_areas": mock_impact_areas,
            "model": "mock",
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    # TODO: at place using a text to identify the impact area
    # we need request the wikidata to fetch possible impact area related with personality
    # then we need abstract the VR context informations to identify the impact area also
    async def _identify_impact_areas_with_openai(self, text: str, model: str, correlation_id: str = None) -> List[Dict[str, Any]]:
        """Use OpenAI to identify impact areas in the text"""
        prompt = f"""
        Analyze the following text and identify the main impact areas.
        Return the result as a JSON array with the following structure for each impact area:
        [
            {{
                "name": "Impact area name",
                "description": "Description of the impact",
                "confidence": 0.95
            }}
        ]

        Text to analyze: "{text}"

        If no clear impact areas are found, return an empty array [].
        Only return the JSON array, no additional text.
        """

        try:
            response = await openai_client.create_completion(
                prompt=prompt,
                model=model,
                correlation_id=correlation_id
            )

            import json
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '[]')
            impact_areas = json.loads(content)
            return impact_areas

        except Exception as e:
            logger.error(
                "Failed to identify impact areas with OpenAI",
                error=str(e),
                correlation_id=correlation_id
            )
            return []


class DefiningSeverityProvider:
    """OpenAI provider for defining severity levels"""

    def supports_model(self, model: str) -> bool:
        return True

    async def define_severity(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Define severity from the given text using OpenAI"""

        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock severity definition (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            return self._mock_severity(text)

        severity = await self._assess_severity_with_openai(text, model, correlation_id)

        return {
            "severity": severity,
            "model": model,
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    def _mock_severity(self, text: str) -> Dict[str, Any]:
        """Mock severity assessment for testing"""
        mock_severity = {
            "level": "medium",
            "score": 5.5,
            "reasoning": "The text describes issues of moderate concern",
            "factors": ["Political tension", "Social unrest", "Economic uncertainty"]
        }

        return {
            "severity": mock_severity,
            "model": "mock",
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    async def _assess_severity_with_openai(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Use OpenAI to assess severity in the text"""
        prompt = f"""
        Analyze the following text and assess its severity level.
        Return the result as a JSON object with the following structure:
        {{
            "level": "low|medium|high|critical",
            "score": 0-10,
            "reasoning": "Explanation of the severity assessment",
            "factors": ["Factor 1", "Factor 2", "Factor 3"]
        }}

        Text to analyze: "{text}"

        Severity levels:
        - low (0-2.5): Minor issues with limited impact
        - medium (2.5-5): Moderate issues requiring attention
        - high (5-7.5): Serious issues with significant impact
        - critical (7.5-10): Severe issues requiring immediate action

        Only return the JSON object, no additional text.
        """

        try:
            response = await openai_client.create_completion(
                prompt=prompt,
                model=model,
                correlation_id=correlation_id
            )

            import json
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '{}')
            severity = json.loads(content)
            return severity

        except Exception as e:
            logger.error(
                "Failed to assess severity with OpenAI",
                error=str(e),
                correlation_id=correlation_id
            )
            return {
                "level": "unknown",
                "score": 0,
                "reasoning": "Failed to assess severity",
                "factors": []
            }


# Global provider instances
defining_topics = DefiningTopicsProvider()
defining_impact_area = DefiningImpactAreaProvider()
defining_severity = DefiningSeverityProvider()
