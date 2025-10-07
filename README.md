# AI Task Processor

A service that polls NestJS APIs for AI tasks and processes them using OpenAI, local Ollama models. Features OAuth2 authentication, multi-tier rate limiting, and comprehensive monitoring.

## Features

- **Text embeddings** generation using OpenAI API, Ollama (local)
- **Processing modes**: `openai`, `ollama`, or `hybrid` (Ollama first, OpenAI fallback)
- **OAuth2 authentication** via Ory Cloud with automatic token refresh
- **Multi-tier rate limiting** with persistent storage (minute/hour/day/week/month)
- **Resilience**: Circuit breakers, retry logic, graceful shutdown

## Processing Modes

- **`openai`**: Uses OpenAI API for all embeddings. **Requires** `OPENAI_API_KEY`. Supports any OpenAI model.
- **`ollama`**: Uses local Ollama models exclusively. `OPENAI_API_KEY` **not required**. Only processes models in `SUPPORTED_MODELS`. Downloads models on startup.
- **`hybrid`**: Tries Ollama first, falls back to OpenAI. **Requires** both Ollama and `OPENAI_API_KEY`.

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with required settings:

```bash
# API Integration (required)
API_BASE_URL=http://localhost:3000

# OAuth2 Authentication (required)
ORY_PROJECT_SLUG=your-project-slug
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret

# Processing Mode
PROCESSING_MODE=openai  # or ollama, hybrid

# OpenAI API Key (required for openai/hybrid, optional for ollama)
OPENAI_API_KEY=sk-your-key

# Ollama Models (for ollama/hybrid modes)
SUPPORTED_MODELS=["nomic-embed-text","dengcao/Qwen3-Embedding-0.6B:Q8_0"]
```

### 2. Start Services

```bash
docker-compose up -d
docker-compose logs -f ai-task-processor
```

Ollama models download automatically on first startup when using `ollama` or `hybrid` mode.

## Configuration

All configuration via environment variables (see `.env.example` for complete list).

### Key Settings

**Processing:**
- `PROCESSING_MODE`: `openai`, `ollama`, or `hybrid` (default: `openai`)
- `OPENAI_API_KEY`: OpenAI API key (**required** for `openai`/`hybrid`, **optional** for `ollama`)
- `SUPPORTED_MODELS`: JSON array of Ollama models for `ollama`/`hybrid` modes (default: `["nomic-embed-text","dengcao/Qwen3-Embedding-0.6B:Q8_0"]`)

**Rate Limiting:**
- `RATE_LIMIT_ENABLED`: Enable rate limiting (default: `true`)
- `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_HOUR`, `RATE_LIMIT_PER_DAY`, `RATE_LIMIT_PER_WEEK`, `RATE_LIMIT_PER_MONTH`: Set to `0` to disable individual limits
- `RATE_LIMIT_STRATEGY`: `rolling` or `fixed` (default: `rolling`)

**Advanced:**
- `POLLING_INTERVAL_SECONDS`: Task polling frequency (default: `30`)
- `CONCURRENCY_LIMIT`: Max parallel tasks (default: `5`)
- `CIRCUIT_BREAKER_THRESHOLD`: Failures before circuit opens (default: `5`)

## API Integration

Integrates with NestJS APIs via OAuth2-protected endpoints:

- `GET /api/ai-tasks/pending?limit=10` - Fetch pending tasks
- `PATCH /api/ai-tasks/:id` - Update task status/results

### Task Format
```json
{
  "_id": "task-id",
  "type": "text_embedding",
  "state": "pending",
  "content": {"text": "Text to embed", "model": "nomic-embed-text"},
  "callbackRoute": "verification_update_embedding",
  "callbackParams": {"targetId": "doc-id", "field": "embedding"},
  "createdAt": "2024-01-01T00:00:00.000Z"
}
```

### Processing Flow
1. Poll `/api/ai-tasks/pending` every 30 seconds with OAuth2 Bearer token
2. Validate model is supported by current processing mode
3. Generate embeddings via OpenAI or Ollama
4. Update task via `PATCH /api/ai-tasks/:id`
5. Respect rate limits

## Model Management

**OpenAI (cloud):**
- Supports any OpenAI embedding model (e.g., `text-embedding-3-small`, `text-embedding-ada-002`)
- Models hosted by OpenAI, no downloads needed

**Ollama (local):**
- Only processes models in `SUPPORTED_MODELS` configuration
- Auto-downloads on startup (e.g., `nomic-embed-text`, `dengcao/Qwen3-Embedding-0.6B:Q8_0`)
- Models persist in Docker volumes

**Switch modes:** Edit `PROCESSING_MODE` in `.env` and run `docker-compose restart ai-task-processor`

## Monitoring

**Health Endpoints:**
- `:8001/health` - Health check with rate limit status
- `:8001/ready` - Readiness probe
- `:8001/metrics` - Prometheus metrics

**Available Metrics:**
- Task processing (duration, counts by type/status)
- OAuth2 authentication (success/failure rates)
- API requests (by endpoint/method/status)
- OpenAI/Ollama usage (tokens, requests by model)
- Rate limiting (usage, limits, exceeded events)
- Circuit breaker state

**Mock Processing:** Use `OPENAI_API_KEY=your_openai_api_key_here` (placeholder) to enable mock embeddings for testing without API costs.

## Extending the System

**New Task Types:**
1. Add enum to `TaskType` in `ai_task_processor/models/task.py`
2. Create input/output models
3. Implement processor inheriting from `BaseProcessor`
4. Register in `ProcessorFactory.__init__()`

**New AI Providers:**
1. Create provider class inheriting from `EmbeddingProvider` (see `embedding_providers.py`)
2. Implement `supports_model()` and `create_embedding()`
3. Register in `EmbeddingProviderFactory.create_provider()`

## Architecture

- **OAuth2 authentication** with automatic token refresh
- **Circuit breaker** for API resilience
- **Multi-tier rate limiting** with SQLite persistence
- **Graceful shutdown** with signal management
- **Structured logging** with correlation IDs
- **Docker containerization** with health checks

---

## Architecture Diagram

<img width="1862" height="3942" alt="image" src="https://github.com/user-attachments/assets/95b103be-f038-44c0-ae91-87b14139f21c" />
