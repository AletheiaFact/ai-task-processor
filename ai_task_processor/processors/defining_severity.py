from typing import Dict, Any
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
                has_personality=input_data.personalityWikidataId is not None,
                topics_count=len(input_data.topicsWikidataIds)
            )

            personality = None
            if input_data.personalityWikidataId:
                logger.info("Fetching personality data by ID",
                           wikidata_id=input_data.personalityWikidataId)
                personality = await wikidata_client.get_personality_data(
                    wikidata_id=input_data.personalityWikidataId,
                    correlation_id=task.id
                )

            topics_context = []
            for topic_id in input_data.topicsWikidataIds:
                logger.info("Fetching topic data by ID", wikidata_id=topic_id)
                topic_data = await wikidata_client.get_topic_data_by_id(
                    wikidata_id=topic_id,
                    correlation_id=task.id
                )
                topics_context.append(topic_data)

            logger.info("Fetching impact area data by ID",
                       wikidata_id=input_data.impactAreaWikidataId)
            impact_area_context = await wikidata_client.get_impact_area_data_by_id(
                wikidata_id=input_data.impactAreaWikidataId,
                correlation_id=task.id
            )

            enriched_data = {
                "impact_area": impact_area_context,
                "topics": topics_context,
                "personality": personality,
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
