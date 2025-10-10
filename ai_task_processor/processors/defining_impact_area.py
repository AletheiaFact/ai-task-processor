from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, DefiningImpactAreaInput
from ..services.defining_services import defining_impact_area
from ..services.wikidata_client import wikidata_client
from ..utils import get_logger, RetryableError
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class DefiningImpactAreaProcessor(BaseProcessor):
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
                "Identified impact areas from AI model",
                task_id=task.id,
                impact_areas_count=len(result.get("impact_areas", [])),
                correlation_id=task.id
            )

            # Enrich impact areas with Wikidata information
            impact_areas = result.get("impact_areas", [])
            if impact_areas:
                logger.info(
                    "Enriching impact areas with Wikidata",
                    task_id=task.id,
                    impact_areas_count=len(impact_areas),
                    correlation_id=task.id
                )

                try:
                    enriched_impact_areas = await self._enrich_impact_areas_with_wikidata(
                        impact_areas=impact_areas,
                        correlation_id=task.id
                    )
                    result["impact_areas"] = enriched_impact_areas

                    # Log enrichment statistics
                    enriched_count = sum(1 for ia in enriched_impact_areas if ia.get("wikidata"))
                    logger.info(
                        "Wikidata enrichment completed",
                        task_id=task.id,
                        total_impact_areas=len(enriched_impact_areas),
                        enriched_count=enriched_count,
                        correlation_id=task.id
                    )

                except Exception as e:
                    # Don't fail the entire task if Wikidata enrichment fails
                    logger.warning(
                        "Wikidata enrichment failed, continuing with unenriched data",
                        task_id=task.id,
                        error=str(e),
                        correlation_id=task.id
                    )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.SUCCEEDED,
                output_data=result
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

    async def _enrich_impact_areas_with_wikidata(
        self,
        impact_areas: list,
        correlation_id: str = None
    ) -> list:
        """Enrich impact areas with Wikidata information"""
        enriched_impact_areas = []

        for impact_area in impact_areas:
            enriched = impact_area.copy()
            area_name = impact_area.get("name")

            if area_name:
                try:
                    wikidata_info = await wikidata_client.enrich_personality(
                        name=area_name,
                        mentioned_as=area_name,
                        language="en",
                        correlation_id=correlation_id
                    )

                    if wikidata_info:
                        enriched["wikidata"] = wikidata_info
                    else:
                        enriched["wikidata"] = None

                except Exception as e:
                    logger.warning(
                        "Failed to enrich impact area with Wikidata",
                        area_name=area_name,
                        error=str(e),
                        correlation_id=correlation_id
                    )
                    enriched["wikidata"] = None
            else:
                enriched["wikidata"] = None

            enriched_impact_areas.append(enriched)

        return enriched_impact_areas
