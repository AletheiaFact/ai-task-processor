import asyncio
import sys
import httpx
from .utils import setup_logging, get_logger, shutdown_manager
from .scheduler import task_scheduler
from .server import metrics_server
from .config import settings, ProcessingMode
from .services.ollama_client import ollama_client

logger = get_logger(__name__)


async def validate_configuration():
    """Validate critical configuration before starting services"""
    errors = []
    warnings = []

    # Validate API_BASE_URL
    if not settings.api_base_url:
        errors.append("API_BASE_URL is not configured")
    else:
        logger.info("Configuration check", api_base_url=settings.api_base_url)

        # Test API connectivity
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to connect (don't worry about auth yet)
                test_url = f"{settings.api_base_url.rstrip('/')}/health"
                logger.info("Testing API connectivity", test_url=test_url)
                try:
                    response = await client.get(test_url)
                    logger.info("API health check successful", status_code=response.status_code)
                except httpx.ConnectError as e:
                    warnings.append(
                        f"Cannot connect to API at {settings.api_base_url}. "
                        f"Error: {str(e)}. "
                        f"If using Docker, try 'http://host.docker.internal:PORT' instead of 'localhost'"
                    )
                except Exception as e:
                    warnings.append(f"API health check failed: {str(e)}")
        except Exception as e:
            warnings.append(f"Could not validate API connectivity: {str(e)}")

    # Validate OAuth2 configuration
    if not settings.ory_project_slug:
        errors.append("ORY_PROJECT_SLUG is not configured")
    if not settings.oauth2_client_id:
        errors.append("OAUTH2_CLIENT_ID is not configured")
    if not settings.oauth2_client_secret:
        errors.append("OAUTH2_CLIENT_SECRET is not configured")

    if settings.ory_project_slug:
        logger.info("OAuth2 configuration",
                   ory_project_slug=settings.ory_project_slug,
                   client_id=settings.oauth2_client_id[:8] + "..." if settings.oauth2_client_id else "NOT SET")

    # Validate processing mode configuration
    logger.info("Processing mode configuration",
               processing_mode=settings.processing_mode.value)

    if settings.processing_mode in [ProcessingMode.OPENAI, ProcessingMode.HYBRID]:
        if not settings.openai_api_key:
            errors.append(f"OPENAI_API_KEY is required when PROCESSING_MODE={settings.processing_mode.value}")
        elif settings.openai_api_key == "your_openai_api_key_here":
            logger.warning("Using mock OpenAI processing (placeholder API key detected)")
        else:
            logger.info("OpenAI API key configured")

    if settings.processing_mode in [ProcessingMode.OLLAMA, ProcessingMode.HYBRID]:
        logger.info("Ollama configuration",
                   ollama_base_url=settings.ollama_base_url,
                   processing_mode=settings.processing_mode.value)

    if settings.processing_mode == ProcessingMode.OLLAMA:
        if settings.openai_api_key:
            logger.info("OPENAI_API_KEY is set but not required for OLLAMA mode")
        else:
            logger.info("OPENAI_API_KEY not required for OLLAMA-only mode")

    # Log any warnings
    for warning in warnings:
        logger.warning("Configuration warning", warning=warning)

    # Log errors and exit if any critical errors
    if errors:
        logger.error("Configuration validation failed", errors=errors)
        logger.error(
            "Please check your .env file and ensure all required variables are set:\n"
            "- API_BASE_URL (e.g., http://host.docker.internal:3000)\n"
            "- ORY_PROJECT_SLUG\n"
            "- OAUTH2_CLIENT_ID\n"
            "- OAUTH2_CLIENT_SECRET"
        )
        return False

    logger.info("Configuration validation passed")
    return True


async def main():
    try:
        setup_logging()
        logger.info("AI Task Processor starting up")

        # Validate configuration before proceeding
        if not await validate_configuration():
            logger.error("Startup aborted due to configuration errors")
            sys.exit(1)
        
        # Initialize Ollama models if using Ollama processing mode
        if settings.processing_mode in [ProcessingMode.OLLAMA, ProcessingMode.HYBRID]:
            logger.info("Ensuring Ollama models are available", processing_mode=settings.processing_mode)
            try:
                await ollama_client.ensure_models_available(correlation_id="startup")
                logger.info("Ollama model initialization completed")
            except Exception as e:
                logger.error("Failed to initialize Ollama models", error=str(e))
                if settings.processing_mode == ProcessingMode.OLLAMA:
                    logger.error("Cannot proceed without Ollama models in OLLAMA mode")
                    sys.exit(1)
        
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