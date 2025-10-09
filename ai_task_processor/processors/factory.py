from typing import Dict, Optional
from ..models import Task, TaskType
from ..utils import get_logger
from .base_processor import BaseProcessor
from .text_embedding import TextEmbeddingProcessor
from .identifying_data import IdentifyingDataProcessor

logger = get_logger(__name__)


class ProcessorFactory:
    def __init__(self):
        self._processors: Dict[str, BaseProcessor] = {
            TaskType.TEXT_EMBEDDING: TextEmbeddingProcessor(),
            TaskType.IDENTIFYING_DATA: IdentifyingDataProcessor()
        }
        
        logger.info(
            "Processor factory initialized",
            available_processors=list(self._processors.keys())
        )
    
    def get_processor(self, task: Task) -> Optional[BaseProcessor]:
        processor = self._processors.get(task.type)
        
        if processor is None:
            logger.warning(
                "No processor found for task type",
                task_id=task.id,
                task_type=task.type,
                available_processors=list(self._processors.keys())
            )
            return None
        
        can_process_result = processor.can_process(task)
        logger.info(
            "Processor can_process check",
            task_id=task.id,
            task_type=task.type,
            processor=processor.__class__.__name__,
            can_process=can_process_result
        )
        
        if not can_process_result:
            logger.warning(
                "Processor cannot handle task",
                task_id=task.id,
                task_type=task.type,
                processor=processor.__class__.__name__
            )
            return None
        
        logger.info(
            "Processor selected successfully",
            task_id=task.id,
            task_type=task.type,
            processor=processor.__class__.__name__
        )
        return processor
    
    def register_processor(self, task_type: str, processor: BaseProcessor):
        self._processors[task_type] = processor
        logger.info(
            "Processor registered",
            task_type=task_type,
            processor=processor.__class__.__name__
        )
    
    def get_supported_task_types(self) -> list:
        return list(self._processors.keys())


processor_factory = ProcessorFactory()