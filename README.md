# AI Task Processor

A service that polls NestJS APIs for AI tasks and processes them using OpenAI, Ollama, or mock data. Handles authentication, rate limiting, monitoring, and error recovery.

## What it does

- Polls your NestJS API every 30 seconds for pending AI tasks
- Processes text embeddings using OpenAI, local Ollama models, or mock data
- Updates task status back to your API with results
- Includes OAuth2 authentication, multi-tier rate limiting, and monitoring

## Core capabilities

- **Text embeddings**: Generate vector embeddings from text content
- **Multiple AI providers**: OpenAI API, local Ollama models, or mock processing
- **Rate limiting**: Per-minute/hour/day/week/month limits with persistent storage
- **Authentication**: OAuth2 with Ory Cloud integration and auto token refresh  
- **Monitoring**: Prometheus metrics, Grafana dashboards, health checks
- **Resilience**: Circuit breakers, retry logic, graceful error handling

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Ory Cloud project with OAuth2 client configured
- NestJS API with AI task endpoints
- OpenAI API Key (optional - can use mock processing)

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

### Required Configuration
- `API_BASE_URL` - Base URL of the NestJS API (required)
- `ORY_PROJECT_SLUG` - Your Ory Cloud project slug (required)
- `OAUTH2_CLIENT_ID` - OAuth2 client ID from Ory Cloud (required)
- `OAUTH2_CLIENT_SECRET` - OAuth2 client secret from Ory Cloud (required)

### Optional Configuration
- `OPENAI_API_KEY` - OpenAI API key for AI operations (use "your_openai_api_key_here" for mock processing)
- `OAUTH2_SCOPE` - OAuth2 scope for authentication (default: "read write")
- `POLLING_INTERVAL_SECONDS` - How often to poll for new tasks (default: 30)
- `CONCURRENCY_LIMIT` - Max simultaneous task processing (default: 5)
- `REQUEST_TIMEOUT` - HTTP request timeout in seconds (default: 30)
- `CIRCUIT_BREAKER_THRESHOLD` - Circuit breaker failure threshold (default: 5)

## NestJS Integration

The service integrates with NestJS applications using these authenticated endpoints:

- `GET /api/ai-tasks/pending` - Returns list of pending tasks (OAuth2 protected)
- `PATCH /api/ai-tasks/:id` - Updates task status and results (OAuth2 protected)

Expected task format from NestJS (MongoDB schema):
```json
{
  "_id": "task-id",
  "type": "text_embedding",
  "state": "pending",
  "content": {"text": "Text to process", "model": "text-embedding-3-small"},
  "callbackRoute": "verification_update_embedding",
  "callbackParams": {"documentId": "doc-id"},
  "createdAt": "2024-01-01T00:00:00.000Z",
  "updatedAt": null
}
```

### Authentication
The service uses OAuth2 Client Credentials flow via Ory Cloud:
1. Authenticates with your Ory Cloud project using client credentials
2. Obtains access token for API requests
3. Includes `Authorization: Bearer <token>` header in all API calls
4. Automatically refreshes tokens when expired

## Monitoring

### Health Endpoints
- `GET /health` - Basic health check
- `GET /ready` - Readiness probe for Kubernetes
- `GET /metrics` - Prometheus metrics endpoint

### Full Monitoring Stack
Optional monitoring via Docker Compose:
```bash
docker-compose up -d  # Starts processor + monitoring stack
```

Access monitoring tools:
- **Prometheus**: `http://localhost:9090` - Metrics collection and querying
- **Grafana**: `http://localhost:3001` - Dashboards and visualization (admin/admin)

### Available Metrics
- Task processing duration and counts by type/status
- OAuth2 authentication success/failure rates
- API request metrics with endpoint/method/status_code labels
- OpenAI API usage tracking (tokens by model/type)
- Circuit breaker state monitoring
- System resource utilization

## Extending the System

### Adding New Task Types
1. Add enum value to `TaskType` in `ai_task_processor/models/task.py`
2. Create input/output models if needed  
3. Implement processor class inheriting from `BaseProcessor`
4. Register processor in `ProcessorFactory.__init__()`

Example processor implementation:
```python
class NewTaskProcessor(BaseProcessor):
    def can_process(self, task: Task) -> bool:
        return task.type == TaskType.NEW_TASK_TYPE
    
    async def process(self, task: Task) -> TaskResult:
        # Implementation here
        pass
```

### Mock Processing
For development without API costs, set `OPENAI_API_KEY=your_openai_api_key_here` to enable mock processing. The system will generate realistic mock embeddings and usage statistics for testing.

### Production Deployment
This implementation includes production-ready features:
- OAuth2 authentication with token refresh
- Circuit breaker pattern for API resilience
- Comprehensive monitoring and health checks
- Graceful shutdown handling
- Structured logging with correlation IDs
- Docker containerization with proper resource limits