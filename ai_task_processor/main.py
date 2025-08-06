import asyncio
import sys
from .utils import setup_logging, get_logger, shutdown_manager
from .scheduler import task_scheduler
from .server import metrics_server

logger = get_logger(__name__)


async def main():
    try:
        setup_logging()
        logger.info("AI Task Processor starting up")
        
        shutdown_manager.setup_signal_handlers()
        
        tasks = []
        
        scheduler_task = asyncio.create_task(task_scheduler.start())
        tasks.append(scheduler_task)
        
        metrics_task = asyncio.create_task(metrics_server.start())
        tasks.append(metrics_task)
        
        logger.info("All services started, running indefinitely")
        
        await shutdown_manager.wait_for_shutdown()
        
        logger.info("Shutdown signal received, stopping services")
        
        for task in tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("AI Task Processor shutdown complete")
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Unexpected error in main", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())