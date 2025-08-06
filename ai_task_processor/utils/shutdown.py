import asyncio
import signal
from typing import Set, Callable, Optional
from .logger import get_logger

logger = get_logger(__name__)


class GracefulShutdown:
    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._running_tasks: Set[asyncio.Task] = set()
        self._cleanup_callbacks: Set[Callable] = set()
        self._is_shutting_down = False
    
    def setup_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame):
        logger.info("Shutdown signal received", signal=signum)
        if not self._is_shutting_down:
            asyncio.create_task(self.shutdown())
    
    async def shutdown(self):
        if self._is_shutting_down:
            return
        
        self._is_shutting_down = True
        logger.info("Starting graceful shutdown")
        
        self._shutdown_event.set()
        
        logger.info("Waiting for running tasks to complete", task_count=len(self._running_tasks))
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)
        
        logger.info("Running cleanup callbacks", callback_count=len(self._cleanup_callbacks))
        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error("Error in cleanup callback", error=str(e))
        
        logger.info("Graceful shutdown completed")
    
    def add_task(self, task: asyncio.Task):
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
    
    def add_cleanup_callback(self, callback: Callable):
        self._cleanup_callbacks.add(callback)
    
    def is_shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()
    
    async def wait_for_shutdown(self):
        await self._shutdown_event.wait()


shutdown_manager = GracefulShutdown()