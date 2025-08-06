# Aletheia AI Task Manager

A robust AI Task Processor service that polls external APIs for AI tasks, processes them using OpenAI, and reports results back. Built with Python, FastAPI, and Docker with comprehensive monitoring and observability features.

## 🚀 Features

- **Producer-Consumer Architecture**: Efficiently polls for pending AI tasks and processes them concurrently
- **OpenAI Integration**: Built-in support for text embeddings and other OpenAI operations
- **Circuit Breaker Pattern**: Graceful handling of API failures with automatic recovery
- **Comprehensive Monitoring**: Prometheus metrics, structured logging, and Grafana dashboards
- **Docker Support**: Full containerization with Docker Compose for easy deployment
- **Extensible Design**: Easy to add new AI task types and processors
- **Graceful Shutdown**: Ensures in-flight tasks complete before termination
- **Retry Logic**: Exponential backoff with jitter for resilient API operations

## 🏗️ Architecture

### Core Components

1. **TaskScheduler**: Polls `/api/ai-tasks/pending` every 30 seconds
2. **ProcessorFactory**: Routes tasks to appropriate processors based on task type
3. **Processors**: Execute AI operations (currently text embeddings via OpenAI)
4. **APIClient**: Updates task status via PATCH `/api/ai-tasks/:id`
5. **MetricsServer**: Exposes Prometheus metrics at `:8001/metrics`

### Processing Flow

```
External API → TaskScheduler → ProcessorFactory → AI Processor → Results → External API
                                     ↓
                              Metrics & Logging
```

## 🛠️ Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (recommended)
- OpenAI API Key
- External API endpoint for task management

### Local Development

1. **Clone and navigate to the repository**
   ```bash
   git clone <repository-url>
   cd aletheia-ai-task-manager
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API_BASE_URL and OPENAI_API_KEY
   ```

4. **Run the application**
   ```bash
   python run.py
   ```

### Docker Development (Recommended)

1. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start the service with monitoring stack**
   ```bash
   docker-compose up -d
   ```

3. **Start only the AI task processor**
   ```bash
   docker-compose up -d ai-task-processor
   ```

4. **View logs**
   ```bash
   docker-compose logs -f ai-task-processor
   ```

5. **Stop services**
   ```bash
   docker-compose down
   ```

## ⚙️ Configuration

All configuration is handled through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | Required | Base URL of the external API |
| `OPENAI_API_KEY` | Required | OpenAI API key for AI operations |
| `POLLING_INTERVAL_SECONDS` | 30 | How often to poll for new tasks |
| `CONCURRENCY_LIMIT` | 5 | Max simultaneous task processing |
| `MAX_RETRIES` | 3 | Retry attempts for failed operations |
| `REQUEST_TIMEOUT` | 30 | HTTP request timeout (seconds) |
| `OPENAI_TIMEOUT` | 60 | OpenAI API timeout (seconds) |
| `CIRCUIT_BREAKER_THRESHOLD` | 5 | Failures before circuit breaker opens |
| `METRICS_PORT` | 8001 | Port for metrics server |
| `LOG_LEVEL` | INFO | Logging level |

## 📊 Monitoring

The service includes comprehensive monitoring capabilities:

### Health Endpoints

- `GET /health` - Basic health check
- `GET /ready` - Readiness probe  
- `GET /metrics` - Prometheus metrics

### Monitoring Stack (Optional)

When using Docker Compose, you get:

- **Prometheus**: Metrics collection at `http://localhost:9090`
- **Grafana**: Visualization at `http://localhost:3001` (admin/admin)

### Key Metrics

- Task processing duration and counts by type/status
- API request metrics with endpoint/method/status_code labels
- OpenAI usage tracking (tokens by model/type)
- Circuit breaker state monitoring

## 🔧 Extending the System

### Adding New Task Types

1. Add enum value to `TaskType` in `models/task.py`
2. Create input/output models if needed
3. Implement processor class inheriting from `BaseProcessor`
4. Register in `ProcessorFactory.__init__()`

Example:
```python
from ai_task_processor.processors.base import BaseProcessor

class MyCustomProcessor(BaseProcessor):
    def can_process(self, task_type: str) -> bool:
        return task_type == "CUSTOM_TASK"
    
    async def process(self, task_data: dict) -> dict:
        # Your custom processing logic
        return {"result": "processed"}
```

### Adding New AI Providers

Follow the pattern in `services/openai_client.py` - create dedicated client with retry logic and metric collection.

## 📝 API Integration

Your external API should implement these endpoints:

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

## 🐳 Docker

### Build and Run

```bash
# Build image
docker build -t ai-task-processor .

# Run container
docker run -d \
  --name ai-task-processor \
  -p 8001:8001 \
  -e API_BASE_URL=your_api_url \
  -e OPENAI_API_KEY=your_key \
  ai-task-processor
```

### Health Checks

The Docker setup includes health checks that verify the metrics endpoint is responding.

## 🔒 Security

- API keys are loaded from environment variables
- No secrets are logged or committed to version control
- Circuit breaker prevents API abuse
- Graceful error handling prevents crashes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the logs: `docker-compose logs ai-task-processor`
2. Verify configuration in `.env`
3. Ensure external API is accessible
4. Check OpenAI API key is valid

## 🎯 Roadmap

- [ ] Support for additional AI providers (Anthropic, Azure OpenAI)
- [ ] Web UI for task monitoring
- [ ] Advanced task scheduling (cron-like)
- [ ] Task priority queues
- [ ] Batch processing capabilities