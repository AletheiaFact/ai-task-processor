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
        Analyze the following text and identify the main BROAD TOPICS discussed.

        IMPORTANT REQUIREMENTS:
        1. Return topic names in Portuguese (pt-BR)
        2. Use GENERAL categories that exist in knowledge bases (e.g., "Crime", "Política", "Economia", "Saúde")
        3. Avoid overly specific event descriptions
        4. Use single-word or simple 2-word topics when possible

        Return the result as a JSON array with the following structure for each topic found:
        [
            {{
                "name": "Broad topic name in Portuguese",
                "confidence": 0.95,
                "context": "Brief context of the topic in the text"
            }}
        ]

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

            logger.info(
                "OpenAI full response",
                response=response,
                correlation_id=correlation_id
            )

            import json
            content = response.get('choices', [{}])[0].get('text', '[]')

            logger.info(
                "Raw OpenAI response content before JSON parsing",
                content=content,
                content_type=type(content),
                correlation_id=correlation_id
            )

            topics = json.loads(content)

            logger.info(
                "Parsed topics from OpenAI",
                topics=topics,
                topics_count=len(topics),
                correlation_id=correlation_id
            )

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
        """Define impact area from the given text using OpenAI"""

        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock impact area definition (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            return self._mock_impact_areas(text)

        impact_area = await self._identify_impact_areas_with_openai(text, model, correlation_id)

        return {
            "impact_area": impact_area,
            "model": model,
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    def _mock_impact_areas(self, text: str) -> Dict[str, Any]:
        """Mock impact area identification for testing"""
        mock_impact_area = {
            "name": "Social Impact",
            "description": "Affects social structures and relationships",
            "confidence": 0.90
        }

        return {
            "impact_area": mock_impact_area,
            "model": "mock",
            "usage": {"prompt_tokens": len(text.split()), "total_tokens": len(text.split())}
        }

    # TODO: at place using a text to identify the impact area
    # we need request the wikidata to fetch possible impact area related with personality
    # then we need abstract the VR context informations to identify the impact area also
    async def _identify_impact_areas_with_openai(self, text: str, model: str, correlation_id: str = None) -> Dict[str, Any]:
        """Use OpenAI to identify the primary impact area in the text"""
        prompt = f"""
        Analyze the following text and identify the PRIMARY impact area.
        IMPORTANT: Return the impact area name and description in Portuguese (pt-BR).

        Return the result as a JSON object with the following structure:
        {{
            "name": "Impact area name in Portuguese",
            "description": "Description of the impact in Portuguese",
            "confidence": 0.95
        }}

        Text to analyze: "{text}"

        Focus on identifying the SINGLE most relevant impact area.
        Only return the JSON object, no additional text.
        """

        try:
            response = await openai_client.create_completion(
                prompt=prompt,
                model=model,
                correlation_id=correlation_id
            )

            logger.info(
                "OpenAI full response",
                response=response,
                correlation_id=correlation_id
            )

            import json
            content = response.get('choices', [{}])[0].get('text', '{}')

            logger.info(
                "Raw OpenAI response content before JSON parsing",
                content=content,
                content_type=type(content),
                correlation_id=correlation_id
            )

            impact_area = json.loads(content)

            logger.info(
                "Parsed impact area from OpenAI",
                impact_area=impact_area,
                correlation_id=correlation_id
            )

            return impact_area

        except Exception as e:
            logger.error(
                "Failed to identify impact area with OpenAI",
                error=str(e),
                correlation_id=correlation_id
            )
            return {}


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
            content = response.get('choices', [{}])[0].get('text', '{}')
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
