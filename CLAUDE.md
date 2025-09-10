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
# Edit .env with your configuration (see Configuration section)
```

**Run the application:**
```bash
python run.py
```

### Docker Development (Recommended)
**Run with Docker Compose:**
```bash
# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Start all services (AI processor + Ollama + monitoring)
docker-compose up -d

# Start with Ollama for local LLM processing
docker-compose up -d ollama ai-task-processor

# Start with monitoring stack
docker-compose up -d ai-task-processor prometheus grafana

# View logs
docker-compose logs -f ai-task-processor
docker-compose logs -f ollama

# Stop services
docker-compose down
```

### Ollama Local LLM Setup
**Setup Ollama for local embedding processing:**
```bash
# Start Ollama service
docker-compose up -d ollama

# Download embedding models
docker-compose exec ollama ollama pull nomic-embed-text
docker-compose exec ollama ollama pull dengcao/Qwen3-Embedding-0.6B:Q8_0

# Set processing mode to use Ollama
echo "PROCESSING_MODE=ollama" >> .env

# Start AI processor
docker-compose up -d ai-task-processor
```

### Required Configuration
Before running, configure these required environment variables in `.env`:

**API Integration:**
- `API_BASE_URL`: Your NestJS API endpoint (e.g., `http://host.docker.internal:3000`)

**OAuth2/Ory Cloud Authentication:**
- `ORY_PROJECT_SLUG`: Your Ory Cloud project slug
- `OAUTH2_CLIENT_ID`: OAuth2 client ID from Ory Cloud
- `OAUTH2_CLIENT_SECRET`: OAuth2 client secret from Ory Cloud
- `OAUTH2_SCOPE`: OAuth2 scopes (default: "read write")

**OpenAI (Optional):**
- `OPENAI_API_KEY`: OpenAI API key (leave as placeholder to use mock processing)

### Rate Limiting Examples
**Example 1: Burst Protection with Daily Limits**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=20        # Allow bursts up to 20 tasks/minute
RATE_LIMIT_PER_HOUR=100         # 100 tasks/hour steady rate
RATE_LIMIT_PER_DAY=500          # 500 tasks/day quota
```

**Example 2: Budget Control (Weekly/Monthly)**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_WEEK=2000        # Max 2000 tasks per week
RATE_LIMIT_PER_MONTH=7500       # Max 7500 tasks per month
RATE_LIMIT_STRATEGY=rolling     # Rolling windows vs fixed calendar periods
```

**Example 3: Conservative Rate Limiting**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=5         # Slow and steady processing
RATE_LIMIT_PER_DAY=200          # Conservative daily limit
RATE_LIMIT_STRATEGY=fixed       # Calendar-based windows (00:00-23:59)
```

### Monitoring Stack
The Docker Compose setup includes comprehensive monitoring:
- **Prometheus**: Metrics collection at `http://localhost:9090`
- **Grafana**: Visualization at `http://localhost:3001` (admin/admin)
- **AI Task Processor**: Health and metrics at `http://localhost:8001`

## Architecture Overview

This is an **AI Task Processor** service that polls an external NestJS API for AI tasks, processes them using OpenAI (or mock processing), and reports results back. The architecture follows a **producer-consumer pattern** with these key components:

### Core Flow
1. **OAuth2 Authentication** - Authenticates with Ory Cloud using client credentials flow
2. **TaskScheduler** - Polls `/api/ai-tasks/pending` every 30 seconds with Bearer token
3. **RateLimiter** - Checks multi-tier limits before processing (minute/hour/day/week/month)
4. **ProcessorFactory** - Routes tasks to appropriate processors based on task type
5. **Processors** - Execute AI operations (text embeddings via OpenAI, Ollama, or mock data)
6. **APIClient** - Updates task status via PATCH `/api/ai-tasks/:id` with results
7. **MetricsServer** - Exposes Prometheus metrics at `:8001/metrics`

### Key Architectural Patterns

**OAuth2 Authentication**: Ory Cloud integration with automatic token refresh:
- Client credentials flow for machine-to-machine authentication
- Token caching with automatic refresh before expiry
- Circuit breaker integration for auth failures

**Processor Pattern**: New AI task types are added by:
1. Creating a processor class inheriting from `BaseProcessor`
2. Implementing `process()` and `can_process()` methods  
3. Registering it in `ProcessorFactory._processors`

**Mock Processing**: When `OPENAI_API_KEY=your_openai_api_key_here` (placeholder), the system uses mock data:
- Generates realistic embedding vectors for testing
- Supports flexible content formats (string or dictionary)
- Full end-to-end testing without API costs

**Circuit Breaker**: `APIClient` includes circuit breaker logic to handle API failures gracefully - switches to "open" state after 5 consecutive failures, then "half-open" for recovery testing.

**Graceful Shutdown**: `shutdown_manager` coordinates clean shutdown across all components, ensuring in-flight tasks complete before termination.

**Retry Logic**: Exponential backoff with jitter for both API calls and OpenAI requests, with different exception categorization (retryable vs non-retryable).

**Multi-Tier Rate Limiting**: Hierarchical rate limiting system with persistent storage:
- Supports minute, hour, day, week, and month limits simultaneously
- Rolling and fixed window strategies available
- SQLite-based persistence for long-term counters (survives restarts)
- In-memory optimization for short-term limits (minute/hour)
- Automatic database cleanup and counter management
- Integrated with Prometheus metrics and health endpoints
- Graceful handling when limits are exceeded (skip processing, continue service)

## Configuration System

All configuration via environment variables through Pydantic Settings in `config/settings.py`. Key settings:

**Core Settings:**
- `API_BASE_URL`: Target NestJS API endpoint for task retrieval/updates
- `POLLING_INTERVAL_SECONDS`: Task polling frequency (default: 30)
- `CONCURRENCY_LIMIT`: Max simultaneous task processing (default: 5)

**Authentication (Required):**
- `ORY_PROJECT_SLUG`: Ory Cloud project identifier
- `OAUTH2_CLIENT_ID`: OAuth2 client ID for machine-to-machine auth
- `OAUTH2_CLIENT_SECRET`: OAuth2 client secret
- `OAUTH2_SCOPE`: OAuth2 scopes (default: "read write")

**AI Processing:**
- `OPENAI_API_KEY`: OpenAI API key (use placeholder for mock processing)
- `PROCESSING_MODE`: AI processing mode - "openai", "ollama", or "hybrid" (default: "openai")

**Ollama Configuration (when using local LLM processing):**
- `OLLAMA_BASE_URL`: Ollama server URL (default: "http://localhost:11434")
- `OLLAMA_TIMEOUT`: Request timeout for Ollama operations (default: 120 seconds)
- `OLLAMA_MAX_RETRIES`: Max retry attempts for Ollama requests (default: 3)
- `OLLAMA_MODEL_DOWNLOAD_TIMEOUT`: Timeout for model downloads (default: 600 seconds)

**Advanced Settings:**
- `MAX_RETRIES`: Retry attempts for failed operations (default: 3)
- `CIRCUIT_BREAKER_THRESHOLD`: Failures before circuit breaker opens (default: 5)
- `METRICS_PORT`: Prometheus metrics server port (default: 8001)

**Multi-Tier Rate Limiting:**
- `RATE_LIMIT_ENABLED`: Enable/disable rate limiting (default: true)
- `RATE_LIMIT_STRATEGY`: Window strategy - "rolling" or "fixed" (default: rolling)
- `RATE_LIMIT_STORAGE_PATH`: Database path for persistent limits (default: /app/data/rate_limits.db)
- `RATE_LIMIT_PER_MINUTE`: Tasks per minute limit (0 = disabled)
- `RATE_LIMIT_PER_HOUR`: Tasks per hour limit (0 = disabled)
- `RATE_LIMIT_PER_DAY`: Tasks per day limit (0 = disabled)
- `RATE_LIMIT_PER_WEEK`: Tasks per week limit (0 = disabled)
- `RATE_LIMIT_PER_MONTH`: Tasks per month limit (0 = disabled)

## Monitoring & Observability

**Structured Logging**: All components use `structlog` with JSON output and correlation IDs for request tracing.

**Prometheus Metrics**: Comprehensive metrics collection including:
- Task processing duration and counts by type/status
- API request metrics with endpoint/method/status_code labels  
- OAuth2 authentication metrics (token generation, failures)
- OpenAI usage tracking (tokens by model/type)
- Ollama usage tracking (requests by model/status, estimated tokens)
- Circuit breaker state monitoring
- Multi-tier rate limiting metrics (current usage, limits, exceeded events by time period)

**Health Endpoints**:
- `/health` - Basic health check with rate limiting status
- `/ready` - Readiness probe
- `/metrics` - Prometheus metrics including rate limiting data

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

## NestJS API Integration

The service integrates with a NestJS API that expects specific task and response formats:

**Expected Task Format:**
```typescript
{
  _id: string,
  type: "text_embedding",
  state: "pending" | "in_progress" | "succeeded" | "failed",
  content: string | { text: string, model?: string },
  callbackRoute: "verification_update_embedding",
  callbackParams: { targetId: string, field: string },
  createdAt: Date,
  updatedAt?: Date
}
```

**Update Response Format:**
```typescript
{
  state: "succeeded" | "failed",
  result: number[] | null  // For embeddings: array of floats
}
```

**Required NestJS M2M Guard Configuration:**
```typescript
// Update your M2M guard to use correct config paths:
const hydraBasePath = this.configService.get<string>("ory.admin_url");
const introspectionToken = this.configService.get<string>("ory.access_token");
```