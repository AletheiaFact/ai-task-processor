from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import uvicorn
import asyncio

from .config import settings
from .utils import get_logger, shutdown_manager
from .services import metrics

logger = get_logger(__name__)

app = FastAPI(title="AI Task Processor Metrics", version="1.0.0")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-task-processor"}


@app.get("/metrics")
async def get_metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/ready")
async def readiness_check():
    return {"status": "ready", "service": "ai-task-processor"}


class MetricsServer:
    def __init__(self):
        self.server = None
        self.is_running = False
    
    async def start(self):
        if self.is_running:
            logger.warning("Metrics server already running")
            return
        
        self.is_running = True
        
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=settings.metrics_port,
            log_level=settings.log_level.lower(),
            access_log=False
        )
        
        self.server = uvicorn.Server(config)
        
        shutdown_manager.add_cleanup_callback(self.stop)
        
        logger.info("Starting metrics server", port=settings.metrics_port)
        
        try:
            await self.server.serve()
        except Exception as e:
            logger.error("Metrics server error", error=str(e))
            raise
    
    async def stop(self):
        if not self.is_running or not self.server:
            return
        
        logger.info("Stopping metrics server")
        
        self.server.should_exit = True
        self.is_running = False
        
        logger.info("Metrics server stopped")


metrics_server = MetricsServer()