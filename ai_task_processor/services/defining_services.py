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
    """Provider for defining severity with AI reasoning"""

    def supports_model(self, model: str) -> bool:
        """Check if model is supported - accepts any OpenAI model"""
        return True

    async def define_severity(
        self,
        enriched_data: Dict[str, Any],
        model: str,
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """
        Define severity level using AI reasoning

        Args:
            enriched_data: Dictionary containing:
                - impact_area: Wikidata-enriched impact area data
                - topics: List of Wikidata-enriched topic data
                - personality: Optional Wikidata-enriched personality data
                - text: Text content being verified
            model: OpenAI model to use for reasoning
            correlation_id: Correlation ID for tracking

        Returns:
            Dictionary with severity classification result
        """
        # Check if using mock mode
        if settings.openai_api_key == "your_openai_api_key_here":
            logger.info(
                "Using mock severity definition (no API key provided)",
                model=model,
                correlation_id=correlation_id
            )
            return self._mock_severity(enriched_data)

        # Build prompt for AI reasoning
        prompt = self._build_severity_prompt(enriched_data)

        # Classify severity with AI
        severity_enum = await self._classify_severity_with_ai(prompt, model, correlation_id)

        return {
            "severity": severity_enum,
            "model": model,
            "usage": {"model_used": model}
        }

    def _mock_severity(self, enriched_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock severity classification for testing without API key"""
        return {
            "severity": "medium_2",
            "model": "mock",
            "usage": {"model_used": "mock"}
        }

    def _build_severity_prompt(self, enriched_data: Dict[str, Any]) -> str:
        """
        Build structured prompt for AI to reason about severity
        Includes all Wikidata contextual signals for holistic analysis
        Falls back to text-only analysis if Wikidata enrichment is unavailable
        """
        impact_area = enriched_data.get("impact_area")
        topics = enriched_data.get("topics", [])
        personalities = enriched_data.get("personalities", [])  # Changed to array
        text = enriched_data.get("text", "")

        prompt = """You are a reasoning model for classifying the severity of fact-check verification requests.

Given contextual information about the impact area, topics, personalities (if present), and text content,
analyze how severe or important this verification is according to these severity levels:

**Severity Levels (from highest to lowest):**
- critical: Extremely urgent, widespread impact, high public safety concern (e.g., public health emergencies, election fraud, national security threats)
- high_3: Very high severity with significant immediate consequences (e.g., major political scandals, serious misinformation affecting public policy)
- high_2: High severity with substantial potential impact (e.g., influential figures spreading false health information)
- high_1: High severity with notable implications (e.g., misinformation about significant social/economic issues)
- medium_3: Moderate-high severity (e.g., false claims by regional influencers, local policy issues)
- medium_2: Moderate severity (e.g., debatable claims with moderate reach)
- medium_1: Moderate-low severity (e.g., minor factual errors with limited impact)
- low_3: Low-moderate severity (e.g., entertainment/celebrity rumors with some public interest)
- low_2: Low severity with minimal impact (e.g., trivial misinformation, very limited reach)
- low_1: Very low severity, limited scope (e.g., personal disputes, negligible audience)

**Geographic Context:**
Most verification requests originate from BRAZIL (Brazilian Portuguese content, Brazilian personalities/topics).
However, you must evaluate severity considering BOTH:
1. **Brazilian Impact:** How does this affect Brazilian society, politics, public health, or safety?
2. **Global Relevance:** Does this have international implications or involve globally significant topics?

A claim may have HIGH severity in Brazilian context even with moderate global metrics, and vice versa.

**Context to Analyze:**

"""

        # Impact Area Context (if available)
        if impact_area:
            prompt += f"""**Impact Area:**
- Label: {impact_area.get('label', 'Unknown')}
- Description: {impact_area.get('description', 'N/A')}
- Sitelinks (global recognition): {impact_area.get('sitelinks', 0)}
- Statements (data completeness): {impact_area.get('statements', 0)}
- Inbound links (centrality in knowledge graph): {impact_area.get('inbound_links', 0)}
- Pageviews (30-day public interest): {impact_area.get('pageviews', 0)}

"""
        else:
            prompt += """**Impact Area:**
- Not available (Wikidata enrichment failed) - Use text content for analysis

"""

        # Topics Context (if available)
        if topics:
            prompt += "**Topics:**\n"
            for idx, topic in enumerate(topics, 1):
                prompt += f"""  {idx}. {topic.get('label', 'Unknown')}
     - Description: {topic.get('description', 'N/A')}
     - Sitelinks: {topic.get('sitelinks', 0)}
     - Statements: {topic.get('statements', 0)}
     - Inbound links: {topic.get('inbound_links', 0)}
     - Pageviews: {topic.get('pageviews', 0)}

"""
        else:
            prompt += """**Topics:**
- Not available (Wikidata enrichment failed) - Use text content for analysis

"""

        # Personalities Context (if exists - array)
        if personalities:
            prompt += "**Personalities:**\n"
            for idx, personality in enumerate(personalities, 1):
                prompt += f"""  {idx}. {personality.get('label', 'Unknown')}
     - Description: {personality.get('description', 'N/A')}
     - Sitelinks: {personality.get('sitelinks', 0)}
     - Statements: {personality.get('statements', 0)}
     - Inbound links: {personality.get('inbound_links', 0)}
     - Pageviews: {personality.get('pageviews', 0)}
     - Social followers: {personality.get('followers', 0)}
     - Number of positions held: {len(personality.get('positions', []))}
     - Number of awards: {len(personality.get('awards', []))}

"""
        else:
            prompt += """**Personalities:**
- Not identified or Wikidata enrichment not available

"""

        if text:
            prompt += f"""**Text Content:**
{text}

"""

        prompt += """**How to Interpret Wikidata Metrics:**

**Sitelinks (Global Recognition):**
- 200+: Globally significant topic/person (e.g., "Climate Change", "Barack Obama")
- 100-199: High international recognition (e.g., "Nuclear Power", major politicians)
- 50-99: Notable regional or specialized recognition
- 10-49: Moderate recognition, often local/national figures
- <10: Limited recognition, local issues or emerging topics

**Pageviews (Public Interest - 30 days):**
- 1M+: Extremely high public interest, trending globally
- 100k-1M: High public interest, widely discussed
- 10k-100k: Moderate interest, significant audience
- 1k-10k: Low-moderate interest
- <1k: Minimal public interest

**Inbound Links (Knowledge Graph Centrality):**
- 10k+: Highly connected, fundamental concept
- 1k-10k: Well-connected, important topic
- 100-1k: Moderately connected
- <100: Loosely connected, specialized

**Statements (Data Completeness):**
- 500+: Very comprehensive, well-documented
- 200-499: Well-documented
- 100-199: Moderately documented
- <100: Limited documentation

**For Personalities - Social Followers:**
- 10M+: Massive reach, national/international influencer
- 1M-10M: Large reach, significant public figure
- 100k-1M: Moderate reach, regional influencer
- 10k-100k: Small-moderate reach
- <10k: Limited reach

**Analysis Instructions:**
1. **Evaluate Brazilian Context First:** Is this about Brazilian politics, society, or public figures? Consider local impact severity.
2. **Assess Global Relevance:** Does this involve international topics or have cross-border implications?
3. **Personality Influence:** If present, how much reach do they have? High followers + Brazilian context = higher severity.
4. **Topic Urgency:** Health, politics, safety = higher severity. Entertainment, sports = lower severity.
5. **Impact Area Scope:** Does this affect public safety, democracy, health, or economic stability?
6. **Public Engagement:** High pageviews indicate active public discussion, raising severity.
7. **Text Content Analysis:** Read the actual claim - what specific harm could misinformation cause?
8. **Fallback Analysis:** If Wikidata metrics are unavailable, rely heavily on text content analysis. Consider the subject matter, potential harm, and likely audience reach based on the content itself.

**Brazilian Context Examples:**
- Brazilian politician with 1M followers spreading election misinformation → HIGH severity (even with moderate global metrics)
- Global warming claim in Brazilian Portuguese about Amazon deforestation → HIGH severity (Brazilian + global relevance)
- Brazilian celebrity entertainment rumor → LOW-MEDIUM severity (limited real-world impact)
- Health misinformation from Brazilian doctor/influencer → HIGH severity (public safety risk)

**IMPORTANT:** Respond with ONLY ONE of the severity enum values listed above. No explanation, just the enum value.

Severity level:"""

        return prompt

    async def _classify_severity_with_ai(
        self,
        prompt: str,
        model: str,
        correlation_id: str
    ) -> str:
        """
        Call OpenAI to classify severity based on contextual reasoning
        Returns one of the SeverityEnum values
        """
        logger.info("Calling OpenAI for severity classification",
                   model=model, correlation_id=correlation_id)

        response = await openai_client.create_completion(
            prompt=prompt,
            model=model,
            correlation_id=correlation_id
        )

        # Extract severity enum from response
        severity_text = response["choices"][0]["text"].strip().lower()

        # Validate and normalize enum value
        valid_severities = [
            "critical", "high_3", "high_2", "high_1",
            "medium_3", "medium_2", "medium_1",
            "low_3", "low_2", "low_1"
        ]

        # Clean up response (remove any extra text)
        for severity in valid_severities:
            if severity in severity_text:
                logger.info(
                    "AI classified severity",
                    severity=severity,
                    correlation_id=correlation_id
                )
                return severity

        # Fallback to medium_2 if AI response is unclear
        logger.warning(
            "AI returned unclear severity, using fallback",
            response_text=severity_text,
            correlation_id=correlation_id
        )
        return "medium_2"




# Global provider instances
defining_topics = DefiningTopicsProvider()
defining_impact_area = DefiningImpactAreaProvider()
defining_severity = DefiningSeverityProvider()
