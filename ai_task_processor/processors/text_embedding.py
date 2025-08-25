from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, TextEmbeddingInput
from ..services import embedding_provider
from ..utils import get_logger, RetryableError
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class TextEmbeddingProcessor(BaseProcessor):
    def can_process(self, task: Task) -> bool:
        return task.type == TaskType.TEXT_EMBEDDING
    
    async def process(self, task: Task) -> TaskResult:
        try:
            if not task.content:
                raise ValueError("Task content is missing or None")
            
            # Handle different content formats - with new requirement, model should always be provided
            if isinstance(task.content, str):
                # Legacy support: if content is a string, use default model
                input_data = TextEmbeddingInput(
                    text=task.content,
                    model="text-embedding-3-small"  # Default fallback
                )
                logger.warning(
                    "Task content is string format, using default model",
                    task_id=task.id,
                    default_model=input_data.model
                )
            elif isinstance(task.content, dict):
                # Validate that model is provided in the content
                if "model" not in task.content:
                    raise ValueError("Model is required in task content")
                input_data = TextEmbeddingInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")
            
            logger.info(
                "Processing text embedding task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )
            
            # Use the embedding provider to create embedding
            result = await embedding_provider.create_embedding(
                text=input_data.text,
                model=input_data.model,
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
                "Text embedding processing failed with retryable error",
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
                "Text embedding processing failed",
                task_id=task.id,
                error=str(e)
            )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Text embedding failed: {str(e)}"
            )