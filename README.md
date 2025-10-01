# AI Task Processor

A service that polls NestJS APIs for AI tasks and processes them using OpenAI, local Ollama models, or mock data. Features configuration-based model management, OAuth2 authentication, rate limiting, and comprehensive monitoring.

<img width="1862" height="3942" alt="image" src="https://github.com/user-attachments/assets/95b103be-f038-44c0-ae91-87b14139f21c" />


## What it does

- Polls your NestJS API every 30 seconds for pending AI tasks
- Processes text embeddings using OpenAI API, local Ollama models, or mock data
- Updates task status back to your API with results
- Includes OAuth2 authentication, multi-tier rate limiting, and monitoring

## Core capabilities

- **Text embeddings**: Generate vector embeddings from text content
- **Multiple AI providers**: OpenAI API (cloud), Ollama (local), or mock processing
- **Processing modes**: `openai`, `ollama`, or `hybrid` (Ollama with OpenAI fallback)
- **Configuration-based models**: Define supported models in environment variables
- **Rate limiting**: Per-minute/hour/day/week/month limits with persistent storage
- **Authentication**: OAuth2 with Ory Cloud integration and auto token refresh  
- **Monitoring**: Prometheus metrics, health checks, structured logging
- **Resilience**: Circuit breakers, retry logic, graceful error handling

## Processing Modes

### OpenAI Processing (`PROCESSING_MODE=openai`)
- Uses OpenAI API for all embeddings
- Supports any OpenAI embedding model requested in tasks
- Requires valid `OPENAI_API_KEY`
- No local model downloads needed
- Flexible - automatically supports new OpenAI models

### Ollama Processing (`PROCESSING_MODE=ollama`)
- Uses local Ollama models for all embeddings
- Only processes models defined in `SUPPORTED_MODELS` configuration
- Downloads configured models automatically on startup
- Completely local processing - no external API calls
- Controlled - only uses pre-approved models

### Hybrid Processing (`PROCESSING_MODE=hybrid`)
- Tries Ollama first, falls back to OpenAI if unavailable
- Best of both worlds - local efficiency with cloud reliability
- Requires both Ollama setup and valid `OPENAI_API_KEY`

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your configuration:

**Required for all modes:**
```bash
# API Integration
API_BASE_URL=http://localhost:3000

# OAuth2 Authentication (Ory Cloud)
ORY_PROJECT_SLUG=your-project-slug
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
```

**For OpenAI/Hybrid modes:**
```bash
PROCESSING_MODE=openai  # or hybrid
OPENAI_API_KEY=sk-your-real-openai-key
```

**For Ollama/Hybrid modes:**
```bash
PROCESSING_MODE=ollama  # or hybrid
SUPPORTED_MODELS=["nomic-embed-text","all-minilm"]
```

### 2. Start the Service

**All services (recommended):**
```bash
docker-compose up -d
docker-compose logs -f ai-task-processor
```

**Step-by-step:**
```bash
# Start Ollama first (if using local processing)
docker-compose up -d ollama

# Start AI processor (downloads models automatically)
docker-compose up -d ai-task-processor

# Watch logs
docker-compose logs -f ai-task-processor
```

### 3. What You'll See

**Startup logs:**
```
AI Task Processor starting up
Ensuring Ollama models are available (if using ollama/hybrid mode)
Downloading missing supported model: nomic-embed-text
Model downloaded successfully: nomic-embed-text
All services started, running indefinitely
```

**Task processing logs:**
```
OAuth2 token generated successfully
Found pending tasks: 1
Processing text embedding task: model=nomic-embed-text
Embedding created successfully: 768 dimensions
Task processing completed: status=succeeded
```

## Configuration

### Core Settings
```bash
# Processing Mode (required)
PROCESSING_MODE=ollama  # openai, ollama, or hybrid

# API Integration (required)
API_BASE_URL=http://localhost:3000

# OAuth2 Authentication (required)
ORY_PROJECT_SLUG=your-project-slug
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
```

### OpenAI Configuration
```bash
# Required for openai/hybrid modes
OPENAI_API_KEY=sk-your-real-openai-key

# Optional
OPENAI_TIMEOUT=60
```

### Ollama Configuration
```bash
# Required for ollama/hybrid modes
SUPPORTED_MODELS=["nomic-embed-text","all-minilm"]

# Optional
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_TIMEOUT=120
OLLAMA_MODEL_DOWNLOAD_TIMEOUT=600
```

### Rate Limiting Configuration
```bash
# Multi-tier rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=20
RATE_LIMIT_PER_HOUR=100  
RATE_LIMIT_PER_DAY=500
RATE_LIMIT_PER_WEEK=2000
RATE_LIMIT_PER_MONTH=7500
RATE_LIMIT_STRATEGY=rolling  # or fixed
```

### Other Settings
```bash
# Polling and processing
POLLING_INTERVAL_SECONDS=30
CONCURRENCY_LIMIT=5
MAX_RETRIES=3

# Timeouts and circuit breaker
REQUEST_TIMEOUT=30
CIRCUIT_BREAKER_THRESHOLD=5

# Monitoring
METRICS_PORT=8001
LOG_LEVEL=INFO
```

## NestJS Integration

The service integrates with NestJS applications using these OAuth2-protected endpoints:

- `GET /api/ai-tasks/pending?limit=10` - Returns pending tasks
- `PATCH /api/ai-tasks/:id` - Updates task status and results

### Expected Task Format
```json
{
  "_id": "68b89107952364b0aad89c1d",
  "type": "text_embedding", 
  "state": "pending",
  "content": {
    "text": "Text to embed",
    "model": "nomic-embed-text"
  },
  "callbackRoute": "verification_update_embedding",
  "callbackParams": {"documentId": "doc-id"},
  "createdAt": "2024-01-01T00:00:00.000Z"
}
```

### Task Processing Flow
1. **Polling**: Service polls `/api/ai-tasks/pending` every 30 seconds
2. **Authentication**: Uses OAuth2 Bearer token from Ory Cloud
3. **Model Validation**: Checks if requested model is supported by current provider
4. **Processing**: Generates embeddings using OpenAI API or local Ollama
5. **Callback**: Updates task via `PATCH /api/ai-tasks/:id` with results
6. **Rate Limiting**: Respects configured rate limits across all time periods

## Model Management

### OpenAI Models (Cloud Processing)
- **Flexible**: Supports any OpenAI embedding model
- **Current models**: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- **Future-proof**: Automatically works with new OpenAI models
- **No downloads**: Models hosted by OpenAI

### Ollama Models (Local Processing)
- **Controlled**: Only supports models defined in `SUPPORTED_MODELS`
- **Auto-download**: Downloads configured models on startup
- **Popular models**: `nomic-embed-text`, `all-minilm`, `mxbai-embed-large`
- **Persistent**: Models stored in Docker volumes

### Switching Processing Modes
Change `PROCESSING_MODE` in `.env` and restart:

```bash
# Switch to OpenAI
echo "PROCESSING_MODE=openai" >> .env
docker-compose restart ai-task-processor

# Switch to local Ollama
echo "PROCESSING_MODE=ollama" >> .env  
docker-compose restart ai-task-processor

# Switch to hybrid (Ollama + OpenAI fallback)
echo "PROCESSING_MODE=hybrid" >> .env
docker-compose restart ai-task-processor
```

## Monitoring

### Health Endpoints
- `GET :8001/health` - Basic health check with rate limiting status
- `GET :8001/ready` - Readiness probe for Kubernetes
- `GET :8001/metrics` - Prometheus metrics endpoint

### Available Metrics
- Task processing duration and counts by type/status
- OAuth2 authentication success/failure rates
- API request metrics with endpoint/method/status_code labels
- OpenAI API usage tracking (tokens by model/type)
- Ollama usage tracking (requests by model/status)
- Rate limiting metrics (current usage, limits, exceeded events)
- Circuit breaker state monitoring

### Development with Mock Processing
For development without API costs, use placeholder OpenAI key:
```bash
PROCESSING_MODE=openai
OPENAI_API_KEY=your_openai_api_key_here  # Enables mock processing
```

The system generates realistic mock embeddings and usage statistics for testing.

## Extending the System

### Adding New Task Types
1. Add enum value to `TaskType` in `ai_task_processor/models/task.py`
2. Create input/output models if needed  
3. Implement processor class inheriting from `BaseProcessor`
4. Register processor in `ProcessorFactory.__init__()`

### Adding New AI Providers
Follow the pattern in `embedding_providers.py`:
1. Create provider class inheriting from `EmbeddingProvider`
2. Implement `supports_model()` and `create_embedding()` methods
3. Add provider to `EmbeddingProviderFactory.create_provider()`

## Production Deployment

This implementation includes production-ready features:
- OAuth2 authentication with automatic token refresh
- Circuit breaker pattern for API resilience  
- Multi-tier rate limiting with persistent storage
- Comprehensive monitoring and health checks
- Graceful shutdown handling with signal management
- Structured logging with correlation IDs
- Docker containerization with health checks
- Configuration-based model management
- Support for both cloud and local AI processing
