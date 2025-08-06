import asyncio
from typing import List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .services import APIClient, metrics
from .processors import processor_factory
from .models import Task, TaskResult, TaskStatus
from .utils import get_logger, shutdown_manager

logger = get_logger(__name__)


class TaskScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.semaphore = asyncio.Semaphore(settings.concurrency_limit)
        self.is_running = False
        
        logger.info(
            "Task scheduler initialized",
            polling_interval=settings.polling_interval_seconds,
            concurrency_limit=settings.concurrency_limit
        )
    
    async def start(self):
        if self.is_running:
            logger.warning("Scheduler already running")
            return
        
        self.is_running = True
        
        self.scheduler.add_job(
            self._poll_and_process_tasks,
            trigger=IntervalTrigger(seconds=settings.polling_interval_seconds),
            id='task_polling',
            max_instances=1,
            coalesce=True
        )
        
        self.scheduler.start()
        
        shutdown_manager.add_cleanup_callback(self.stop)
        
        logger.info("Task scheduler started")
    
    async def stop(self):
        if not self.is_running:
            return
        
        logger.info("Stopping task scheduler")
        
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        
        logger.info("Task scheduler stopped")
    
    async def _poll_and_process_tasks(self):
        if shutdown_manager.is_shutdown_requested():
            logger.info("Shutdown requested, skipping task polling")
            return
        
        try:
            async with APIClient() as api_client:
                tasks = await api_client.get_pending_tasks(limit=settings.concurrency_limit * 2)
                
                if not tasks:
                    logger.debug("No pending tasks found")
                    return
                
                logger.info("Found pending tasks", task_count=len(tasks))
                
                processing_tasks = []
                for task in tasks:
                    if shutdown_manager.is_shutdown_requested():
                        break
                    
                    task_coroutine = self._process_single_task(task, api_client)
                    processing_task = asyncio.create_task(task_coroutine)
                    shutdown_manager.add_task(processing_task)
                    processing_tasks.append(processing_task)
                
                if processing_tasks:
                    await asyncio.gather(*processing_tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error("Error in task polling cycle", error=str(e), exc_info=True)
    
    async def _process_single_task(self, task: Task, api_client: APIClient):
        async with self.semaphore:
            if shutdown_manager.is_shutdown_requested():
                logger.info("Shutdown requested, skipping task processing", task_id=task.id)
                return
            
            processor = processor_factory.get_processor(task)
            if not processor:
                result = TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error_message=f"No processor available for task type: {task.type}"
                )
            else:
                metrics.start_task_processing(task.id, task.type)
                
                try:
                    result = await processor.execute_with_error_handling(task)
                finally:
                    metrics.end_task_processing(task.id, task.type, result.status)
            
            success = await api_client.update_task_status(task.id, result)
            if not success:
                logger.error("Failed to update task status in API", task_id=task.id)


task_scheduler = TaskScheduler()