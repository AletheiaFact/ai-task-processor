# Aletheia AI Task Manager

A proof of concept AI Task Processor service that demonstrates polling an external API for AI tasks, processing them using OpenAI, and reporting results back. This is a simple implementation to showcase the integration pattern between a task management system and AI processing capabilities.

## Purpose

This POC demonstrates how to build a service that:
- Polls an external API for pending AI tasks
- Processes tasks using OpenAI's API
- Updates task status and results back to the external system
- Provides basic monitoring and logging capabilities

## Architecture

The service follows a producer-consumer pattern with these components:

1. **TaskScheduler** - Polls `/api/ai-tasks/pending` every 30 seconds
2. **ProcessorFactory** - Routes tasks to appropriate processors based on task type
3. **Processors** - Execute AI operations (currently supports text embeddings)
4. **APIClient** - Updates task status via PATCH `/api/ai-tasks/:id`
5. **MetricsServer** - Exposes basic metrics at `:8001/metrics`

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API Key
- External API for task management

### Running with Docker

1. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API_BASE_URL and OPENAI_API_KEY
   ```

2. Start the service:
   ```bash
   docker-compose up -d ai-task-processor
   ```

3. View logs:
   ```bash
   docker-compose logs -f ai-task-processor
   ```

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Run the application:
   ```bash
   python run.py
   ```

## Configuration

Key environment variables:

- `API_BASE_URL` - Base URL of the external API (required)
- `OPENAI_API_KEY` - OpenAI API key for AI operations (required)
- `POLLING_INTERVAL_SECONDS` - How often to poll for new tasks (default: 30)
- `CONCURRENCY_LIMIT` - Max simultaneous task processing (default: 5)

## API Integration

The external API should provide these endpoints:

- `GET /api/ai-tasks/pending` - Returns list of pending tasks
- `PATCH /api/ai-tasks/:id` - Updates task status and results

Expected task format:
```json
{
  "id": "task-id",
  "type": "TEXT_EMBEDDING",
  "data": {"text": "Text to process"},
  "state": "PENDING"
}
```

## Monitoring

Basic monitoring endpoints:
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

Optional monitoring stack via Docker Compose:
- Prometheus at `http://localhost:9090`
- Grafana at `http://localhost:3001` (admin/admin)

## Adding New Task Types

1. Add task type to `models/task.py`
2. Create processor class inheriting from `BaseProcessor`
3. Register processor in `ProcessorFactory`

## Notes

This is a proof of concept implementation. For production use, consider adding proper error handling, authentication, rate limiting, and comprehensive testing.