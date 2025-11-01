from typing import Dict, Any
import asyncio
from ..models import Task, TaskResult, TaskStatus, TaskType, DefiningSeverityInput
from ..services.defining_services import defining_severity
from ..services.wikidata_client import wikidata_client
from ..utils import get_logger, RetryableError
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class DefiningSeverityProcessor(BaseProcessor):
    """
    Processor for defining verification request severity using AI reasoning

    Follows the standard pattern:
    - Validates input and extracts model from task.content
    - Fetches rich Wikidata context (sitelinks, pageviews, inbound links, etc.)
    - Uses defining_severity service to classify with AI
    - Returns SeverityEnum value based on AI reasoning
    """

    def can_process(self, task: Task) -> bool:
        result = task.type == TaskType.DEFINING_SEVERITY
        logger.info(
            "DefiningSeverityProcessor can_process check",
            task_id=task.id,
            task_type=task.type,
            expected_type=TaskType.DEFINING_SEVERITY,
            can_process=result
        )
        return result

    async def process(self, task: Task) -> TaskResult:
        """
        Process severity definition task using AI reasoning
        Follows standard pattern: validate input, fetch context, call service
        """
        try:
            logger.info(
                "Starting DefiningSeverityProcessor.process",
                task_id=task.id,
                task_type=task.type,
                content_type=type(task.content),
                content_value=task.content
            )

            if not task.content:
                raise ValueError("Task content is missing or None")

            if isinstance(task.content, dict):
                if "model" not in task.content:
                    raise ValueError("Model is required in task content")
                input_data = DefiningSeverityInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")

            if not defining_severity.supports_model(input_data.model):
                raise ValueError(
                    f"Requested model '{input_data.model}' is not supported. "
                    f"Supported models: OpenAI models"
                )

            logger.info(
                "Processing defining severity task",
                task_id=task.id,
                model=input_data.model,
                personalities_count=len(input_data.personalities),
                topics_count=len(input_data.topics),
                has_impact_area=input_data.impactArea is not None
            )

            async def enrich_personality(personality):
                """Helper function to enrich a single personality"""
                if personality.wikidataId:
                    try:
                        logger.info(
                            "Fetching personality data by ID",
                            wikidata_id=personality.wikidataId,
                            name=personality.name,
                            correlation_id=task.id
                        )
                        personality_data = await wikidata_client.get_personality_data(
                            wikidata_id=personality.wikidataId,
                            correlation_id=task.id
                        )
                        return personality_data
                    except Exception as e:
                        logger.warning(
                            "Failed to fetch personality data, using provided name",
                            wikidata_id=personality.wikidataId,
                            name=personality.name,
                            error=str(e),
                            correlation_id=task.id
                        )
                        return {
                            "label": personality.name,
                            "source": "user_provided"
                        }
                else:
                    logger.info(
                        "Using personality name directly (no Wikidata ID)",
                        name=personality.name,
                        correlation_id=task.id
                    )
                    return {
                        "label": personality.name,
                        "source": "user_provided"
                    }

            if input_data.personalities:
                logger.info(
                    "Enriching personalities in parallel",
                    task_id=task.id,
                    personalities_count=len(input_data.personalities),
                    correlation_id=task.id
                )
                personalities_tasks = [enrich_personality(p) for p in input_data.personalities]
                personalities_context = await asyncio.gather(*personalities_tasks)
            else:
                personalities_context = []

            async def enrich_topic(topic):
                """Helper function to enrich a single topic"""
                if topic.wikidataId:
                    try:
                        logger.info(
                            "Fetching topic data by ID",
                            wikidata_id=topic.wikidataId,
                            name=topic.name,
                            language=topic.language,
                            correlation_id=task.id
                        )
                        topic_data = await wikidata_client.get_topic_data_by_id(
                            wikidata_id=topic.wikidataId,
                            correlation_id=task.id
                        )
                        return topic_data
                    except Exception as e:
                        logger.warning(
                            "Failed to fetch topic data, using provided name",
                            wikidata_id=topic.wikidataId,
                            name=topic.name,
                            error=str(e),
                            correlation_id=task.id
                        )
                        return {
                            "label": topic.name,
                            "language": topic.language,
                            "source": "user_provided"
                        }
                else:
                    logger.info(
                        "Using topic name directly (no Wikidata ID)",
                        name=topic.name,
                        language=topic.language,
                        correlation_id=task.id
                    )
                    return {
                        "label": topic.name,
                        "language": topic.language,
                        "source": "user_provided"
                    }

            if input_data.topics:
                logger.info(
                    "Enriching topics in parallel",
                    task_id=task.id,
                    topics_count=len(input_data.topics),
                    correlation_id=task.id
                )
                topics_tasks = [enrich_topic(t) for t in input_data.topics]
                topics_context = await asyncio.gather(*topics_tasks)
            else:
                topics_context = []

            impact_area_context = None
            if input_data.impactArea:
                if input_data.impactArea.wikidataId:
                    try:
                        logger.info(
                            "Fetching impact area data by ID",
                            wikidata_id=input_data.impactArea.wikidataId,
                            name=input_data.impactArea.name,
                            language=input_data.impactArea.language,
                            correlation_id=task.id
                        )
                        impact_area_context = await wikidata_client.get_impact_area_data_by_id(
                            wikidata_id=input_data.impactArea.wikidataId,
                            correlation_id=task.id
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to fetch impact area data, using provided name",
                            wikidata_id=input_data.impactArea.wikidataId,
                            name=input_data.impactArea.name,
                            error=str(e),
                            correlation_id=task.id
                        )
                        impact_area_context = {
                            "label": input_data.impactArea.name,
                            "language": input_data.impactArea.language,
                            "source": "user_provided"
                        }
                else:
                    logger.info(
                        "Using impact area name directly (no Wikidata ID)",
                        name=input_data.impactArea.name,
                        language=input_data.impactArea.language,
                        correlation_id=task.id
                    )
                    impact_area_context = {
                        "label": input_data.impactArea.name,
                        "language": input_data.impactArea.language,
                        "source": "user_provided"
                    }

            enriched_data = {
                "impact_area": impact_area_context,
                "topics": topics_context,
                "personalities": personalities_context,
                "text": input_data.text
            }

            result = await defining_severity.define_severity(
                enriched_data=enriched_data,
                model=input_data.model,
                correlation_id=task.id
            )

            logger.info(
                "Severity classification completed",
                task_id=task.id,
                severity=result.get("severity"),
                model=result.get("model"),
                correlation_id=task.id
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.SUCCEEDED,
                output_data={"severity": result.get("severity")}
            )

        except RetryableError as e:
            logger.warning(
                "Severity processing failed with retryable error",
                task_id=task.id,
                error=str(e)
            )
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Retryable error: {str(e)}"
            )

        except Exception as e:
            logger.error(
                "Severity processing failed",
                task_id=task.id,
                error=str(e),
                exc_info=True
            )
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Severity calculation failed: {str(e)}"
            )
