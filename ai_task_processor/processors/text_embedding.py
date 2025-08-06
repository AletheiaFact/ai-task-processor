from typing import Dict, Any
import random
from ..models import Task, TaskResult, TaskStatus, TaskType, TextEmbeddingInput
from ..services import openai_client
from ..utils import get_logger
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class TextEmbeddingProcessor(BaseProcessor):
    def can_process(self, task: Task) -> bool:
        return task.type == TaskType.TEXT_EMBEDDING
    
    async def process(self, task: Task) -> TaskResult:
        try:
            if not task.content:
                raise ValueError("Task content is missing or None")
            
            # Handle different content formats
            if isinstance(task.content, str):
                # If content is a string, create a default structure
                input_data = TextEmbeddingInput(
                    text=task.content,
                    model="text-embedding-3-small"
                )
            elif isinstance(task.content, dict):
                input_data = TextEmbeddingInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")
            
            logger.info(
                "Processing text embedding task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )
            
            # Check if OpenAI key is provided, otherwise use mock data
            if settings.openai_api_key == "your_openai_api_key_here":
                logger.info(
                    "Using mock embedding data (no OpenAI API key provided)",
                    task_id=task.id
                )
                # Generate mock embedding vector (1536 dimensions for text-embedding-3-small)
                mock_embedding = [random.uniform(-1, 1) for _ in range(1536)]
                result = {
                    "embedding": mock_embedding,
                    "model": input_data.model,
                    "usage": {
                        "prompt_tokens": len(input_data.text.split()),
                        "total_tokens": len(input_data.text.split())
                    }
                }
            else:
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