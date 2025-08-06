from abc import ABC, abstractmethod
from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus
from ..utils import get_logger

logger = get_logger(__name__)


class BaseProcessor(ABC):
    def __init__(self):
        self.processor_name = self.__class__.__name__
    
    @abstractmethod
    async def process(self, task: Task) -> TaskResult:
        pass
    
    @abstractmethod
    def can_process(self, task: Task) -> bool:
        pass
    
    async def execute_with_error_handling(self, task: Task) -> TaskResult:
        try:
            logger.info(
                "Starting task processing",
                task_id=task.id,
                task_type=task.type,
                processor=self.processor_name
            )
            
            result = await self.process(task)
            
            logger.info(
                "Task processing completed",
                task_id=task.id,
                status=result.status,
                processor=self.processor_name
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Task processing failed",
                task_id=task.id,
                error=str(e),
                processor=self.processor_name,
                exc_info=True
            )
            
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"{self.processor_name} error: {str(e)}"
            )