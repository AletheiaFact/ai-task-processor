# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start Commands

### Local Development
**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Set up environment:**
```bash
cp .env.example .env
# Edit .env with your API_BASE_URL and OPENAI_API_KEY
```

**Run the application:**
```bash
python run.py
```

### Docker Development
**Run with Docker Compose (recommended):**
```bash
# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the service with monitoring stack
docker-compose up -d

# Start only the AI task processor
docker-compose up -d ai-task-processor

# View logs
docker-compose logs -f ai-task-processor

# Stop services
docker-compose down
```

**Build and run Docker image directly:**
```bash
docker build -t ai-task-processor .
docker run -d \
  --name ai-task-processor \
  -p 8001:8001 \
  -e API_BASE_URL=your_api_url \
  -e OPENAI_API_KEY=your_key \
  ai-task-processor
```

### Monitoring Stack
The Docker Compose setup includes optional monitoring:
- **Prometheus**: Metrics collection at `http://localhost:9090`
- **Grafana**: Visualization at `http://localhost:3001` (admin/admin)

## Architecture Overview

This is an **AI Task Processor** service that polls an external API for AI tasks, processes them using OpenAI, and reports results back. The architecture follows a **producer-consumer pattern** with these key components:

### Core Flow
1. **TaskScheduler** polls `/api/ai-tasks/pending` every 30 seconds
2. **ProcessorFactory** routes tasks to appropriate processors based on task type
3. **Processors** execute AI operations (currently text embeddings via OpenAI)
4. **APIClient** updates task status via PATCH `/api/ai-tasks/:id`
5. **MetricsServer** exposes Prometheus metrics at `:8001/metrics`

### Key Architectural Patterns

**Processor Pattern**: New AI task types are added by:
1. Creating a processor class inheriting from `BaseProcessor`
2. Implementing `process()` and `can_process()` methods  
3. Registering it in `ProcessorFactory._processors`

**Circuit Breaker**: `APIClient` includes circuit breaker logic to handle API failures gracefully - switches to "open" state after 5 consecutive failures, then "half-open" for recovery testing.

**Graceful Shutdown**: `shutdown_manager` coordinates clean shutdown across all components, ensuring in-flight tasks complete before termination.

**Retry Logic**: Exponential backoff with jitter for both API calls and OpenAI requests, with different exception categorization (retryable vs non-retryable).

## Configuration System

All configuration via environment variables through Pydantic Settings in `config/settings.py`. Key settings:
- `CONCURRENCY_LIMIT`: Max simultaneous task processing (default: 5)
- `POLLING_INTERVAL_SECONDS`: Task polling frequency (default: 30)
- `API_BASE_URL`: Target API endpoint for task retrieval/updates
- `OPENAI_API_KEY`: Required for text embedding operations

## Monitoring & Observability

**Structured Logging**: All components use `structlog` with JSON output and correlation IDs for request tracing.

**Prometheus Metrics**: Comprehensive metrics collection including:
- Task processing duration and counts by type/status
- API request metrics with endpoint/method/status_code labels  
- OpenAI usage tracking (tokens by model/type)
- Circuit breaker state monitoring

**Health Endpoints**:
- `/health` - Basic health check
- `/ready` - Readiness probe
- `/metrics` - Prometheus metrics

## Extending the System

**Adding New Task Types:**
1. Add enum value to `TaskType` in `models/task.py`
2. Create input/output models if needed
3. Implement processor class inheriting from `BaseProcessor`
4. Register in `ProcessorFactory.__init__()`

**Adding New AI Providers:**
Follow the pattern in `services/openai_client.py` - create dedicated client with retry logic and metric collection.

## Error Handling Strategy

**Three-tier error classification:**
- `RetryableError`: Temporary issues (rate limits, timeouts, 5xx errors)
- `NonRetryableError`: Permanent failures (auth errors, 4xx errors)  
- Generic `Exception`: Caught and logged, typically treated as non-retryable

**Task-level resilience**: Failed tasks are marked as `FAILED` status with error messages, but don't crash the entire service.