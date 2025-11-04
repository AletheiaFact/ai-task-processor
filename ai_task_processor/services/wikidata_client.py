import httpx
import asyncio
from datetime import datetime, timedelta
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
        # Proper headers required by Wikidata API to avoid 403 errors
        self.headers = {
            "User-Agent": "AI-Task-Processor/1.0 (https://github.com/AletheiaFact/ai-task-processor) httpx/0.27.0",
            "Accept": "application/json",
            "Accept-Language": "pt,en;q=0.9"
        }

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session with proper headers"""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers,
                follow_redirects=True
            )
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

            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.2)

            response = await session.get(self.base_url, params=params)

            if response.status_code >= 500:
                raise RetryableError(f"Wikidata server error: {response.status_code}")
            elif response.status_code == 403:
                logger.error(
                    "Wikidata 403 Forbidden - check User-Agent header",
                    name=name,
                    correlation_id=correlation_id
                )
                raise NonRetryableError(f"Wikidata access forbidden: {response.status_code}")
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

            await asyncio.sleep(0.2)

            response = await session.get(self.base_url, params=params)

            if response.status_code >= 500:
                raise RetryableError(f"Wikidata server error: {response.status_code}")
            elif response.status_code == 403:
                logger.error(
                    "Wikidata 403 Forbidden - check User-Agent header",
                    entity_id=entity_id,
                    correlation_id=correlation_id
                )
                raise NonRetryableError(f"Wikidata access forbidden: {response.status_code}")
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

    async def enrich_topic(
        self,
        topic: str,
        language: str = "en",
        correlation_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Enrich topic data by searching Wikidata for general concepts/topics.

        This function searches for a broad topic/concept (not necessarily a person)
        and returns structured Wikidata information.

        Args:
            topic: Topic name (e.g., "Crime", "Política", "Economia")
            language: Language code (default: "en")
            correlation_id: Correlation ID for logging

        Returns:
            Wikidata entity info or None if not found
        """
        try:
            results = await self.search_person(
                name=topic,
                language=language,
                limit=10,
                correlation_id=correlation_id
            )

            if not results:
                logger.info(
                    "No Wikidata results found for topic",
                    topic=topic,
                    correlation_id=correlation_id
                )
                return None

            # For topics, we want the most general/popular result
            # Wikidata returns results by relevance, so take the first
            best_match = results[0]

            wikidata_entity = {
                "id": best_match.get("id"),
                "url": best_match.get("url", f"https://www.wikidata.org/wiki/{best_match.get('id')}"),
                "label": best_match.get("label", topic),
                "description": best_match.get("description"),
                "aliases": best_match.get("aliases", [])
            }

            logger.info(
                "Successfully enriched topic with Wikidata",
                topic=topic,
                wikidata_id=wikidata_entity["id"],
                wikidata_label=wikidata_entity["label"],
                correlation_id=correlation_id
            )

            return wikidata_entity

        except RetryableError:
            # Allow retry errors to propagate
            raise

        except Exception as e:
            logger.warning(
                "Failed to enrich topic with Wikidata",
                topic=topic,
                error=str(e),
                correlation_id=correlation_id
            )
            return None

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

    async def get_inbound_links_count(self, wikidata_id: str) -> int:
        """
        Get the count of inbound links (how many other Wikidata entities link to this one)
        Uses SPARQL query to measure centrality in the knowledge graph
        """
        try:
            sparql_query = f"""
            SELECT (COUNT(?item) AS ?count) WHERE {{
              ?item ?property wd:{wikidata_id} .
            }}
            """

            params = {
                "query": sparql_query,
                "format": "json"
            }

            session = await self._get_session()
            response = await session.get(
                "https://query.wikidata.org/sparql",
                params=params,
                timeout=10.0
            )

            if response.status_code != 200:
                logger.warning(
                    "SPARQL query error",
                    status=response.status_code,
                    wikidata_id=wikidata_id
                )
                return 0

            data = response.json()
            results = data.get("results", {}).get("bindings", [])
            if results:
                count_value = results[0].get("count", {}).get("value", "0")
                return int(count_value)

            return 0

        except Exception as e:
            logger.warning(
                "Inbound links fetch failed",
                wikidata_id=wikidata_id,
                error=str(e)
            )
            return 0

    async def get_wikipedia_pageviews(self, wikidata_id: str, entity: Dict) -> int:
        """
        Get Wikipedia pageview count for the past 30 days
        Uses Wikipedia REST API to measure public engagement
        """
        try:
            sitelinks = entity.get("sitelinks", {})
            enwiki = sitelinks.get("enwiki")

            if not enwiki:
                return 0

            article_title = enwiki.get("title", "").replace(" ", "_")

            if not article_title:
                return 0

            session = await self._get_session()

            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")

            url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{article_title}/daily/{start_str}/{end_str}"

            response = await session.get(url, timeout=10.0)

            if response.status_code != 200:
                logger.warning(
                    "Wikipedia pageviews error",
                    status=response.status_code,
                    article_title=article_title
                )
                return 0

            data = response.json()
            items = data.get("items", [])

            total_views = sum(item.get("views", 0) for item in items)

            return total_views

        except Exception as e:
            logger.warning(
                "Wikipedia pageviews fetch failed",
                wikidata_id=wikidata_id,
                error=str(e)
            )
            return 0

    def _extract_numeric_claim(self, claims: Dict, property_id: str, default: float = 0.0) -> float:
        """Extract numeric value from Wikidata claims"""
        if property_id not in claims:
            return default

        claim_list = claims[property_id]
        if claim_list:
            mainsnak = claim_list[0].get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if isinstance(value, dict):
                amount = value.get("amount", default)
                if isinstance(amount, str):
                    amount = amount.lstrip("+")
                return float(amount)
            return float(value)
        return default

    def _extract_item_ids(self, claims: Dict, property_id: str, limit: int = 5) -> list:
        """Extract item IDs from Wikidata claims"""
        if property_id not in claims:
            return []

        ids = []
        for claim in claims[property_id][:limit]:
            mainsnak = claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if isinstance(value, dict) and "id" in value:
                ids.append(value["id"])

        return ids

    async def get_personality_data(
        self,
        wikidata_id: str,
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """
        Fetch and enrich personality data from Wikidata with rich contextual signals
        Returns structured personality data with quantitative and qualitative properties
        """
        logger.info(
            "Fetching personality data",
            wikidata_id=wikidata_id,
            correlation_id=correlation_id
        )

        try:
            entity = await self.get_entity_details(
                entity_id=wikidata_id,
                correlation_id=correlation_id
            )

            if not entity:
                logger.warning(
                    "Personality not found",
                    wikidata_id=wikidata_id,
                    correlation_id=correlation_id
                )
                return self._get_default_personality(wikidata_id)

            claims = entity.get("claims", {})
            labels = entity.get("labels", {}).get("en", {})
            name = labels.get("value", "Unknown")
            description = entity.get("descriptions", {}).get("en", {}).get("value", "")

            sitelinks_count = len(entity.get("sitelinks", {}))
            statements_count = len(claims)

            # Wikidata properties
            followers = self._extract_numeric_claim(claims, "P8687", default=0)  # P8687: social media followers
            occupations = self._extract_item_ids(claims, "P106")  # P106: occupation
            positions = self._extract_item_ids(claims, "P39")  # P39: position held
            awards = self._extract_item_ids(claims, "P166", limit=10)  # P166: award received

            inbound_links, pageviews = await asyncio.gather(
                self.get_inbound_links_count(wikidata_id),
                self.get_wikipedia_pageviews(wikidata_id, entity),
                return_exceptions=True
            )

            if isinstance(inbound_links, Exception):
                logger.warning("Inbound links error", error=str(inbound_links))
                inbound_links = 0
            if isinstance(pageviews, Exception):
                logger.warning("Pageviews error", error=str(pageviews))
                pageviews = 0

            personality_data = {
                "id": wikidata_id,
                "label": name,
                "description": description,
                "sitelinks": sitelinks_count,
                "statements": statements_count,
                "inbound_links": int(inbound_links),
                "pageviews": int(pageviews),
                "followers": int(followers),
                "occupations": occupations,
                "positions": positions,
                "awards": awards,
            }

            logger.info(
                "Personality data fetched",
                wikidata_id=wikidata_id,
                name=name,
                description=description,
                sitelinks=sitelinks_count,
                statements=statements_count,
                inbound_links=inbound_links,
                pageviews=pageviews,
                followers=int(followers),
                occupations_count=len(occupations),
                positions_count=len(positions),
                awards_count=len(awards),
                correlation_id=correlation_id
            )
            return personality_data

        except Exception as e:
            logger.error(
                "Personality fetch failed",
                wikidata_id=wikidata_id,
                error=str(e),
                correlation_id=correlation_id
            )
            return self._get_default_personality(wikidata_id)

    async def get_topic_data_by_id(
        self,
        wikidata_id: str,
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """
        Fetch topic data directly by Wikidata ID (no search needed)
        This is the preferred method when NestJS already provides the ID
        """
        logger.info(
            "Fetching topic data by ID",
            wikidata_id=wikidata_id,
            correlation_id=correlation_id
        )

        try:
            entity = await self.get_entity_details(
                entity_id=wikidata_id,
                correlation_id=correlation_id
            )

            if not entity:
                logger.warning(
                    "Topic entity not found",
                    wikidata_id=wikidata_id,
                    correlation_id=correlation_id
                )
                return self._get_default_topic("Unknown", wikidata_id)

            result = await self._enrich_topic_from_entity(
                entity,
                wikidata_id,
                fallback_name="Unknown"
            )
            logger.info(
                "Topic data fetched by ID",
                wikidata_id=wikidata_id,
                topic_name=result["label"],
                description=result["description"],
                sitelinks=result["sitelinks"],
                statements=result["statements"],
                inbound_links=result["inbound_links"],
                pageviews=result["pageviews"],
                instance_of_count=len(result["instance_of"]),
                correlation_id=correlation_id
            )
            return result

        except Exception as e:
            logger.error(
                "Topic fetch by ID failed",
                wikidata_id=wikidata_id,
                error=str(e),
                correlation_id=correlation_id
            )
            return self._get_default_topic("Unknown", wikidata_id)

    async def get_impact_area_data_by_id(
        self,
        wikidata_id: str,
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """
        Fetch impact area data directly by Wikidata ID with rich contextual signals
        This is the preferred method when NestJS already provides the ID
        """
        logger.info(
            "Fetching impact area data by ID",
            wikidata_id=wikidata_id,
            correlation_id=correlation_id
        )

        try:
            entity = await self.get_entity_details(
                entity_id=wikidata_id,
                correlation_id=correlation_id
            )

            if not entity:
                logger.warning(
                    "Impact area entity not found",
                    wikidata_id=wikidata_id,
                    correlation_id=correlation_id
                )
                return await self._build_impact_area_result("Unknown", wikidata_id, None)

            area_name = entity.get("labels", {}).get("en", {}).get("value", "Unknown")

            result = await self._build_impact_area_result(area_name, wikidata_id, entity)

            logger.info(
                "Impact area data fetched by ID",
                wikidata_id=wikidata_id,
                area_name=area_name,
                description=result["description"],
                sitelinks=result["sitelinks"],
                statements=result["statements"],
                inbound_links=result["inbound_links"],
                pageviews=result["pageviews"],
                instance_of_count=len(result["instance_of"]),
                correlation_id=correlation_id
            )

            return result

        except Exception as e:
            logger.error(
                "Impact area fetch by ID failed",
                wikidata_id=wikidata_id,
                error=str(e),
                correlation_id=correlation_id
            )
            return await self._build_impact_area_result("Unknown", wikidata_id, None)

    async def _enrich_topic_from_entity(
        self,
        entity: Dict,
        wikidata_id: str,
        fallback_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Internal helper: Enrich topic data from a Wikidata entity with rich contextual signals
        Shared logic for both search-based and ID-based topic fetching
        """
        claims = entity.get("claims", {})
        topic_name = entity.get("labels", {}).get("en", {}).get("value", fallback_name)
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")

        sitelinks_count = len(entity.get("sitelinks", {}))
        statements_count = len(claims)

        instance_of = self._extract_item_ids(claims, "P31", limit=5)  # P31: instance of

        inbound_links, pageviews = await asyncio.gather(
            self.get_inbound_links_count(wikidata_id),
            self.get_wikipedia_pageviews(wikidata_id, entity),
            return_exceptions=True
        )

        if isinstance(inbound_links, Exception):
            logger.warning("Inbound links error for topic", error=str(inbound_links))
            inbound_links = 0
        if isinstance(pageviews, Exception):
            logger.warning("Pageviews error for topic", error=str(pageviews))
            pageviews = 0

        return {
            "id": wikidata_id,
            "label": topic_name,
            "description": description,
            "sitelinks": sitelinks_count,
            "statements": statements_count,
            "inbound_links": int(inbound_links),
            "pageviews": int(pageviews),
            "instance_of": instance_of,
        }

    async def _build_impact_area_result(
        self,
        area_name: str,
        wikidata_id: str,
        entity: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Internal helper: Build impact area result with rich contextual signals
        Shared logic for both search-based and ID-based impact area fetching
        """
        if not entity:
            return {
                "id": wikidata_id,
                "label": area_name,
                "description": "",
                "sitelinks": 0,
                "statements": 0,
                "inbound_links": 0,
                "pageviews": 0,
                "instance_of": [],
            }

        claims = entity.get("claims", {})
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")

        sitelinks_count = len(entity.get("sitelinks", {}))
        statements_count = len(claims)

        instance_of = self._extract_item_ids(claims, "P31", limit=5)  # P31: instance of

        inbound_links, pageviews = await asyncio.gather(
            self.get_inbound_links_count(wikidata_id),
            self.get_wikipedia_pageviews(wikidata_id, entity),
            return_exceptions=True
        )

        if isinstance(inbound_links, Exception):
            logger.warning("Inbound links error for impact area", error=str(inbound_links))
            inbound_links = 0
        if isinstance(pageviews, Exception):
            logger.warning("Pageviews error for impact area", error=str(pageviews))
            pageviews = 0

        return {
            "id": wikidata_id,
            "label": area_name,
            "description": description,
            "sitelinks": sitelinks_count,
            "statements": statements_count,
            "inbound_links": int(inbound_links),
            "pageviews": int(pageviews),
            "instance_of": instance_of,
        }

    def _get_default_personality(self, wikidata_id: str) -> Dict[str, Any]:
        """Return default personality data when Wikidata fetch fails"""
        return {
            "id": wikidata_id,
            "label": "Unknown",
            "description": "",
            "sitelinks": 0,
            "statements": 0,
            "inbound_links": 0,
            "pageviews": 0,
            "followers": 0,
            "occupations": [],
            "positions": [],
            "awards": [],
        }

    def _get_default_topic(self, topic: str, wikidata_id: Optional[str] = None) -> Dict[str, Any]:
        """Return default topic data when Wikidata fetch fails"""
        return {
            "id": wikidata_id or "Q000000",
            "label": topic,
            "description": "",
            "sitelinks": 0,
            "statements": 0,
            "inbound_links": 0,
            "pageviews": 0,
            "instance_of": [],
        }


# Global Wikidata client instance
wikidata_client = WikidataClient()
