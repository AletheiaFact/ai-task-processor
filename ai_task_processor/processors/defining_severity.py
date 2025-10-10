from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, DefiningSeverityInput
from ..services.defining_services import defining_severity
from ..services.wikidata_client import wikidata_client
from ..utils import get_logger, RetryableError
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class DefiningSeverityProcessor(BaseProcessor):
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

            # Handle different content formats
            if isinstance(task.content, str):
                default_model = settings.supported_models[0] if settings.supported_models else "o3-mini"
                input_data = DefiningSeverityInput(
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
                input_data = DefiningSeverityInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")

            # Validate that the requested model is supported
            if not defining_severity.supports_model(input_data.model):
                raise ValueError(
                    f"Requested model '{input_data.model}' is not supported. "
                    f"Supported models: {settings.supported_models}"
                )

            logger.info(
                "Processing defining severity task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )

            # Use the defining severity provider to assess severity
            result = await defining_severity.define_severity(
                text=input_data.text,
                model=input_data.model,
                correlation_id=task.id
            )

            logger.info(
                "Assessed severity from AI model",
                task_id=task.id,
                severity_level=result.get("severity", {}).get("level"),
                severity_score=result.get("severity", {}).get("score"),
                correlation_id=task.id
            )

            # Enrich severity with Wikidata information (for severity level classification)
            severity_data = result.get("severity", {})
            if severity_data:
                logger.info(
                    "Enriching severity classification with Wikidata",
                    task_id=task.id,
                    severity_level=severity_data.get("level"),
                    correlation_id=task.id
                )

                try:
                    enriched_severity = await self._enrich_severity_with_wikidata(
                        severity=severity_data,
                        correlation_id=task.id
                    )
                    result["severity"] = enriched_severity

                    # Log enrichment status
                    has_wikidata = enriched_severity.get("wikidata") is not None
                    logger.info(
                        "Wikidata enrichment completed",
                        task_id=task.id,
                        has_wikidata=has_wikidata,
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
                "Defining severity processing failed with retryable error",
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
                "Defining severity processing failed",
                task_id=task.id,
                error=str(e)
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Defining severity failed: {str(e)}"
            )

    async def _enrich_severity_with_wikidata(
        self,
        severity: dict,
        correlation_id: str = None
    ) -> dict:
        """Enrich severity classification with Wikidata information"""
        enriched = severity.copy()
        severity_level = severity.get("level")

        if severity_level:
            try:
                # Search for severity classification or risk level concept in Wikidata
                search_term = f"severity {severity_level}"

                wikidata_info = await wikidata_client.enrich_personality(
                    name=search_term,
                    mentioned_as=severity_level,
                    language="en",
                    correlation_id=correlation_id
                )

                if wikidata_info:
                    enriched["wikidata"] = wikidata_info
                else:
                    enriched["wikidata"] = None

            except Exception as e:
                logger.warning(
                    "Failed to enrich severity with Wikidata",
                    severity_level=severity_level,
                    error=str(e),
                    correlation_id=correlation_id
                )
                enriched["wikidata"] = None
        else:
            enriched["wikidata"] = None

        return enriched
