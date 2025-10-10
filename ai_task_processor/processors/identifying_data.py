from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, IdentifyingDataInput
from ..services import identifying_data
from ..services.wikidata_client import wikidata_client
from ..utils import get_logger, RetryableError
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class IdentifyingDataProcessor(BaseProcessor):
    def can_process(self, task: Task) -> bool:
        result = task.type == TaskType.IDENTIFYING_DATA
        logger.info(
            "IdentifyingDataProcessor can_process check",
            task_id=task.id,
            task_type=task.type,
            expected_type=TaskType.IDENTIFYING_DATA,
            can_process=result
        )
        return result
    
    async def process(self, task: Task) -> TaskResult:
        try:
            logger.info(
                "Starting IdentifyingDataProcessor.process",
                task_id=task.id,
                task_type=task.type,
                content_type=type(task.content),
                content_value=task.content
            )
            
            if not task.content:
                raise ValueError("Task content is missing or None")
            
            # Handle different content formats - with new requirement, model should always be provided
            if isinstance(task.content, str):
                # Legacy support: if content is a string, use first supported model as default
                default_model = settings.supported_models[0] if settings.supported_models else "o3-mini"
                input_data = IdentifyingDataInput(
                    text=task.content,
                    model=default_model
                )
                logger.warning(
                    "Task content is string format, using default supported model",
                    task_id=task.id,
                    default_model=input_data.model
                )
            elif isinstance(task.content, dict):
                # Validate that model is provided in the content
                if "model" not in task.content:
                    raise ValueError("Model is required in task content")
                input_data = IdentifyingDataInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")
            
            # Validate that the requested model is supported
            if not identifying_data.supports_model(input_data.model):
                raise ValueError(
                    f"Requested model '{input_data.model}' is not supported. "
                    f"Supported models: {settings.supported_models}"
                )
            
            logger.info(
                "Processing identifying data task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )
            
            # Use the identifying data provider to create identifying data
            result = await identifying_data.create_identifying_data(
                text=input_data.text,
                model=input_data.model,
                correlation_id=task.id
            )

            logger.info(
                "Identified personalities from AI model",
                task_id=task.id,
                personalities_count=len(result.get("personalities", [])),
                correlation_id=task.id
            )

            # Enrich personalities with Wikidata information
            personalities = result.get("personalities", [])
            if personalities:
                logger.info(
                    "Enriching personalities with Wikidata",
                    task_id=task.id,
                    personalities_count=len(personalities),
                    correlation_id=task.id
                )

                try:
                    enriched_personalities = await wikidata_client.batch_enrich_personalities(
                        personalities=personalities,
                        language="en",  # TODO: Make language configurable
                        correlation_id=task.id
                    )
                    result["personalities"] = enriched_personalities

                    # Log enrichment statistics
                    enriched_count = sum(1 for p in enriched_personalities if p.get("wikidata"))
                    logger.info(
                        "Wikidata enrichment completed",
                        task_id=task.id,
                        total_personalities=len(enriched_personalities),
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
            # For retryable errors, we want the task to remain in pending state
            # so it can be retried later
            logger.warning(
                "Identifying data processing failed with retryable error",
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
                "Identifying data processing failed",
                task_id=task.id,
                error=str(e)
            )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Identifying data failed: {str(e)}"
            )