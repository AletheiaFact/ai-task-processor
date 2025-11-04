from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, DefiningImpactAreaInput
from ..services.defining_services import defining_impact_area
from ..services.wikidata_client import wikidata_client
from ..utils import get_logger, RetryableError
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class DefiningImpactAreaProcessor(BaseProcessor):
    async def _enrich_impact_area_with_wikidata(
        self,
        impact_area: dict,
        task_id: str,
        correlation_id: str = None
    ) -> dict:
        """Enrich impact area with Wikidata information"""
        name = impact_area.get("name", "")
        description = impact_area.get("description", "")
        wikidata_id = None

        if name:
            logger.info(
                "Enriching impact area with Wikidata",
                task_id=task_id,
                impact_area_name=name,
                correlation_id=correlation_id
            )

            try:
                wikidata_info = await wikidata_client.enrich_topic(
                    topic=name,
                    language="pt",
                    correlation_id=correlation_id
                )

                if wikidata_info:
                    wikidata_id = wikidata_info.get("id", "")
                    logger.info(
                        "Wikidata enrichment completed",
                        task_id=task_id,
                        impact_area_name=name,
                        wikidata_id=wikidata_id,
                        correlation_id=correlation_id
                    )
                else:
                    logger.warning(
                        "No Wikidata information found",
                        task_id=task_id,
                        impact_area_name=name,
                        correlation_id=correlation_id
                    )

            except Exception as e:
                logger.warning(
                    "Wikidata enrichment failed, continuing without Wikidata ID",
                    task_id=task_id,
                    impact_area_name=name,
                    error=str(e),
                    correlation_id=correlation_id
                )

        return {
            "name": name,
            "description": description,
            "wikidataId": wikidata_id,
            "language": "pt"
        }

    def can_process(self, task: Task) -> bool:
        result = task.type == TaskType.DEFINING_IMPACT_AREA
        logger.info(
            "DefiningImpactAreaProcessor can_process check",
            task_id=task.id,
            task_type=task.type,
            expected_type=TaskType.DEFINING_IMPACT_AREA,
            can_process=result
        )
        return result

    async def process(self, task: Task) -> TaskResult:
        try:
            logger.info(
                "Starting DefiningImpactAreaProcessor.process",
                task_id=task.id,
                task_type=task.type,
                content_type=type(task.content),
                content_value=task.content
            )

            if not task.content:
                raise ValueError("Task content is missing or None")

            # Handle different content formats
            if isinstance(task.content, str):
                default_model = settings.supported_models[0] if settings.supported_models else "o3-mini"
                input_data = DefiningImpactAreaInput(
                    text=task.content,
                    model=default_model
                )
                logger.warning(
                    "Task content is string format, using default supported model",
                    task_id=task.id,
                    default_model=input_data.model
                )
            elif isinstance(task.content, dict):
                if "model" not in task.content:
                    raise ValueError("Model is required in task content")
                input_data = DefiningImpactAreaInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")

            # Validate that the requested model is supported
            if not defining_impact_area.supports_model(input_data.model):
                raise ValueError(
                    f"Requested model '{input_data.model}' is not supported. "
                    f"Supported models: {settings.supported_models}"
                )

            logger.info(
                "Processing defining impact area task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )

            # Use the defining impact area provider to identify impact areas
            result = await defining_impact_area.define_impact_areas(
                text=input_data.text,
                model=input_data.model,
                correlation_id=task.id
            )

            logger.info(
                "Identified impact area from AI model",
                task_id=task.id,
                impact_area_name=result.get("impact_area", {}).get("name"),
                correlation_id=task.id
            )

            impact_area = result.get("impact_area", {})
            final_result = await self._enrich_impact_area_with_wikidata(
                impact_area=impact_area,
                task_id=task.id,
                correlation_id=task.id
            )

            logger.info(
                "Impact area processing completed successfully",
                task_id=task.id,
                name=final_result.get("name"),
                has_wikidata_id=bool(final_result.get("wikidataId")),
                correlation_id=task.id
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.SUCCEEDED,
                output_data=final_result
            )

        except RetryableError as e:
            logger.warning(
                "Defining impact area processing failed with retryable error",
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
                "Defining impact area processing failed",
                task_id=task.id,
                error=str(e)
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Defining impact area failed: {str(e)}"
            )
