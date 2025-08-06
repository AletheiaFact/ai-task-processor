from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, TextEmbeddingInput
from ..services import openai_client
from ..utils import get_logger
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class TextEmbeddingProcessor(BaseProcessor):
    def can_process(self, task: Task) -> bool:
        return task.type == TaskType.TEXT_EMBEDDING
    
    async def process(self, task: Task) -> TaskResult:
        try:
            input_data = TextEmbeddingInput(**task.input_data)
            
            logger.info(
                "Processing text embedding task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )
            
            result = await openai_client.create_embedding(
                text=input_data.text,
                model=input_data.model,
                correlation_id=task.id
            )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.SUCCEEDED,
                output_data=result
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