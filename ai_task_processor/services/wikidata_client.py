import httpx
import asyncio
from typing import List, Dict, Any, Optional
from ..config import settings
from ..utils import get_logger, retry, RetryableError, NonRetryableError
from .metrics import metrics

logger = get_logger(__name__)


class WikidataClient:
    """Client for interacting with Wikidata API to enrich personality data"""

    def __init__(self):
        self.base_url = "https://www.wikidata.org/w/api.php"
        self.timeout = httpx.Timeout(30.0)
        self._session: Optional[httpx.AsyncClient] = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session"""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    @retry(
        retryable_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
        non_retryable_exceptions=(NonRetryableError,)
    )
    async def search_person(
        self,
        name: str,
        language: str = "en",
        limit: int = 5,
        correlation_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for a person in Wikidata by name.

        Args:
            name: Name of the person to search
            language: Language code (default: "en")
            limit: Maximum number of results (default: 5, max: 50)
            correlation_id: Correlation ID for logging

        Returns:
            List of matching entities with their details
        """
        try:
            logger.info(
                "Searching Wikidata for person",
                name=name,
                language=language,
                limit=limit,
                correlation_id=correlation_id
            )

            session = await self._get_session()

            params = {
                "action": "wbsearchentities",
                "search": name,
                "language": language,
                "limit": limit,
                "format": "json",
                "type": "item"  # Search for items (entities)
            }

            response = await session.get(self.base_url, params=params)

            if response.status_code >= 500:
                raise RetryableError(f"Wikidata server error: {response.status_code}")
            elif response.status_code >= 400:
                raise NonRetryableError(f"Wikidata client error: {response.status_code}")

            data = response.json()

            if "search" not in data:
                logger.warning(
                    "No search results in Wikidata response",
                    name=name,
                    correlation_id=correlation_id
                )
                return []

            results = data["search"]

            logger.info(
                "Wikidata search completed",
                name=name,
                results_count=len(results),
                correlation_id=correlation_id
            )

            return results

        except httpx.RequestError as e:
            logger.warning(
                "Wikidata request error",
                name=name,
                error=str(e),
                correlation_id=correlation_id
            )
            raise RetryableError(f"Wikidata request failed: {e}")

        except Exception as e:
            logger.error(
                "Unexpected Wikidata error",
                name=name,
                error=str(e),
                correlation_id=correlation_id
            )
            raise NonRetryableError(f"Wikidata search failed: {e}")

    async def get_entity_details(
        self,
        entity_id: str,
        language: str = "en",
        correlation_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a Wikidata entity.

        Args:
            entity_id: Wikidata entity ID (e.g., "Q1234")
            language: Language code for labels/descriptions
            correlation_id: Correlation ID for logging

        Returns:
            Entity details including claims/properties
        """
        try:
            logger.info(
                "Fetching Wikidata entity details",
                entity_id=entity_id,
                language=language,
                correlation_id=correlation_id
            )

            session = await self._get_session()

            params = {
                "action": "wbgetentities",
                "ids": entity_id,
                "languages": language,
                "format": "json"
            }

            response = await session.get(self.base_url, params=params)

            if response.status_code >= 500:
                raise RetryableError(f"Wikidata server error: {response.status_code}")
            elif response.status_code >= 400:
                raise NonRetryableError(f"Wikidata client error: {response.status_code}")

            data = response.json()

            if "entities" not in data or entity_id not in data["entities"]:
                logger.warning(
                    "Entity not found in Wikidata",
                    entity_id=entity_id,
                    correlation_id=correlation_id
                )
                return None

            entity = data["entities"][entity_id]

            logger.info(
                "Wikidata entity details retrieved",
                entity_id=entity_id,
                correlation_id=correlation_id
            )

            return entity

        except httpx.RequestError as e:
            logger.warning(
                "Wikidata request error",
                entity_id=entity_id,
                error=str(e),
                correlation_id=correlation_id
            )
            raise RetryableError(f"Wikidata request failed: {e}")

        except Exception as e:
            logger.error(
                "Unexpected Wikidata error",
                entity_id=entity_id,
                error=str(e),
                correlation_id=correlation_id
            )
            raise NonRetryableError(f"Wikidata entity fetch failed: {e}")

    async def enrich_personality(
        self,
        name: str,
        mentioned_as: str = None,
        language: str = "en",
        correlation_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Enrich personality data by searching Wikidata and returning the best match.

        This function searches for a person by name and returns structured Wikidata
        information including ID, label, description, and aliases.

        Args:
            name: Full name of the person
            mentioned_as: How they're mentioned in text (for better matching)
            language: Language code (default: "en")
            correlation_id: Correlation ID for logging

        Returns:
            Wikidata entity info or None if not found
        """
        try:
            # Search using the full name first
            search_query = name
            results = await self.search_person(
                name=search_query,
                language=language,
                limit=5,
                correlation_id=correlation_id
            )

            # If no results with full name and we have a mentioned_as, try that
            if not results and mentioned_as and mentioned_as != name:
                logger.info(
                    "No results for full name, trying mentioned_as",
                    name=name,
                    mentioned_as=mentioned_as,
                    correlation_id=correlation_id
                )
                results = await self.search_person(
                    name=mentioned_as,
                    language=language,
                    limit=5,
                    correlation_id=correlation_id
                )

            if not results:
                logger.info(
                    "No Wikidata results found for person",
                    name=name,
                    mentioned_as=mentioned_as,
                    correlation_id=correlation_id
                )
                return None

            # Take the first result (best match based on Wikidata ranking)
            best_match = results[0]

            # Extract relevant information
            wikidata_entity = {
                "id": best_match.get("id"),
                "url": best_match.get("url", f"https://www.wikidata.org/wiki/{best_match.get('id')}"),
                "label": best_match.get("label", name),
                "description": best_match.get("description"),
                "aliases": best_match.get("aliases", [])
            }

            logger.info(
                "Successfully enriched personality with Wikidata",
                name=name,
                wikidata_id=wikidata_entity["id"],
                correlation_id=correlation_id
            )

            return wikidata_entity

        except RetryableError:
            # Allow retry errors to propagate
            raise

        except Exception as e:
            # Log but don't fail the entire process if Wikidata enrichment fails
            logger.warning(
                "Failed to enrich personality with Wikidata",
                name=name,
                error=str(e),
                correlation_id=correlation_id
            )
            return None

    async def batch_enrich_personalities(
        self,
        personalities: List[Dict[str, Any]],
        language: str = "en",
        correlation_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple personalities with Wikidata information in parallel.

        Args:
            personalities: List of personality dicts with 'name' and optionally 'mentioned_as'
            language: Language code
            correlation_id: Correlation ID for logging

        Returns:
            List of personalities enriched with Wikidata information
        """
        enrichment_tasks = []

        for personality in personalities:
            task = self.enrich_personality(
                name=personality.get("name"),
                mentioned_as=personality.get("mentioned_as"),
                language=language,
                correlation_id=correlation_id
            )
            enrichment_tasks.append(task)

        # Run all enrichment tasks in parallel
        wikidata_results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

        # Combine original personality data with Wikidata enrichment
        enriched_personalities = []
        for i, personality in enumerate(personalities):
            enriched = personality.copy()

            # Add Wikidata info if enrichment succeeded
            wikidata_result = wikidata_results[i]
            if wikidata_result and not isinstance(wikidata_result, Exception):
                enriched["wikidata"] = wikidata_result
            else:
                enriched["wikidata"] = None

            enriched_personalities.append(enriched)

        return enriched_personalities


# Global Wikidata client instance
wikidata_client = WikidataClient()
