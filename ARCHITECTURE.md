# AI Task Processor - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Processing Modes](#processing-modes)
6. [Authentication & Security](#authentication--security)
7. [Rate Limiting](#rate-limiting)
8. [Monitoring & Observability](#monitoring--observability)
9. [Error Handling & Resilience](#error-handling--resilience)
10. [Deployment Architecture](#deployment-architecture)

---

## System Overview

The AI Task Processor is a **production-grade asynchronous task processing service** that:

- Polls a NestJS API for pending AI tasks
- Processes tasks using OpenAI, Ollama (local LLM), or a hybrid approach
- Implements OAuth2 authentication via Ory Cloud
- Enforces multi-tier rate limiting (minute/hour/day/week/month)
- Provides comprehensive Prometheus metrics and monitoring
- Supports graceful shutdown and circuit breaker patterns

**Key Characteristics:**
- **Asynchronous**: Built with Python asyncio for high concurrency
- **Resilient**: Circuit breakers, retry logic, and graceful degradation
- **Observable**: Structured logging with correlation IDs + Prometheus metrics
- **Scalable**: Configurable concurrency with semaphore-based throttling
- **Flexible**: Supports multiple AI providers with hot-swappable configuration

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Task Processor Service                    │
│                                                                   │
│  ┌──────────────┐         ┌─────────────────┐                  │
│  │   Main.py    │────────▶│  Task Scheduler │                  │
│  │  (Entry)     │         │  (APScheduler)  │                  │
│  └──────────────┘         └────────┬────────┘                  │
│                                     │                            │
│                                     ▼                            │
│                          ┌──────────────────┐                   │
│                          │   APIClient      │◀─────OAuth2       │
│                          │  (with Circuit   │      (Ory Cloud)  │
│                          │   Breaker)       │                   │
│                          └─────────┬────────┘                   │
│                                    │                             │
│                                    ▼                             │
│                          ┌──────────────────┐                   │
│                          │  Rate Limiter    │                   │
│                          │  (Multi-tier)    │                   │
│                          └─────────┬────────┘                   │
│                                    │                             │
│                                    ▼                             │
│                          ┌──────────────────┐                   │
│                          │ Processor Factory│                   │
│                          └─────────┬────────┘                   │
│                                    │                             │
│                  ┌─────────────────┼─────────────────┐          │
│                  ▼                 ▼                 ▼           │
│         ┌─────────────┐   ┌──────────────┐  ┌─────────────┐   │
│         │Text Embedding│   │ Identifying  │  │   Future    │   │
│         │  Processor   │   │Data Processor│  │ Processors  │   │
│         └──────┬───────┘   └──────┬───────┘  └─────────────┘   │
│                │                   │                             │
│                ▼                   ▼                             │
│         ┌─────────────────────────────────┐                     │
│         │   Embedding Provider Factory    │                     │
│         │  (OpenAI/Ollama/Hybrid)         │                     │
│         └─────────────────────────────────┘                     │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Metrics Server (FastAPI + Prometheus)          │  │
│  │  /health  │  /ready  │  /metrics                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   External APIs  │
                    │                  │
                    │ • NestJS API     │
                    │ • OpenAI API     │
                    │ • Ollama Server  │
                    │ • Ory Cloud      │
                    └──────────────────┘
```

---

## Core Components

### 1. Main Application (`main.py`)

**Responsibilities:**
- Application bootstrap and lifecycle management
- Initializes logging and configuration
- Ensures Ollama models are downloaded (when needed)
- Sets up signal handlers for graceful shutdown
- Launches concurrent tasks (scheduler + metrics server)

**Key Flow:**
```python
main()
  ├─ setup_logging()
  ├─ ensure_ollama_models_available()  # If using Ollama
  ├─ setup_signal_handlers()
  ├─ start task_scheduler
  ├─ start metrics_server
  └─ wait_for_shutdown()
```

---

### 2. Task Scheduler (`scheduler.py`)

**Responsibilities:**
- Polls NestJS API for pending tasks every 30 seconds (configurable)
- Enforces concurrency limits via asyncio.Semaphore
- Checks rate limits before processing batches
- Dispatches tasks to appropriate processors
- Updates task status back to API

**Key Logic:**
```python
_poll_and_process_tasks():
  ├─ Check rate limits (multi-tier)
  ├─ Fetch pending tasks from API
  ├─ Limit batch size to concurrency_limit
  ├─ For each task:
  │   ├─ Get appropriate processor
  │   ├─ Execute with error handling
  │   └─ Update task status in API
  └─ Record completed tasks for rate limiting
```

**Configuration:**
- `POLLING_INTERVAL_SECONDS`: How often to poll (default: 30)
- `CONCURRENCY_LIMIT`: Max simultaneous tasks (default: 5)

---

### 3. API Client (`services/api_client.py`)

**Responsibilities:**
- HTTP communication with NestJS API
- OAuth2 authentication (Bearer tokens)
- Circuit breaker pattern for fault tolerance
- Retry logic with exponential backoff
- Metrics collection for API calls

**Circuit Breaker States:**
- **Closed** (normal): Requests flow through
- **Open** (failing): Requests blocked after threshold failures
- **Half-Open** (recovering): Testing if service recovered

**Key Methods:**
- `get_pending_tasks(limit)`: Fetch tasks with GET `/api/ai-tasks/pending`
- `update_task_status(task_id, result)`: Update via PATCH `/api/ai-tasks/:id`

**Error Classification:**
- **Retryable**: 5xx errors, timeouts, connection errors, 401 (token refresh)
- **Non-Retryable**: 4xx errors (except 401), auth failures

---

### 4. Processor System (`processors/`)

**Architecture Pattern:** Factory + Strategy Pattern

#### Base Processor (`base_processor.py`)
Abstract base class defining processor interface:
- `process(task)`: Execute task processing logic
- `can_process(task)`: Validate if processor can handle task
- `execute_with_error_handling(task)`: Wrapper for metrics + error handling

#### Processor Factory (`factory.py`)
Routes tasks to appropriate processors:
```python
{
  TaskType.TEXT_EMBEDDING: TextEmbeddingProcessor(),
  TaskType.IDENTIFYING_DATA: IdentifyingDataProcessor()
}
```

#### Text Embedding Processor (`text_embedding.py`)
- Processes `text_embedding` tasks
- Extracts text and model from task content
- Delegates to Embedding Provider Factory
- Validates model support before processing

#### Identifying Data Processor (`identifying_data.py`)
- Processes `identifying_data` tasks (extracting personalities from text)
- Uses LLM models (e.g., o3-mini)
- Returns structured personality data
- Future: Wikidata integration (see TODO in code)

---

### 5. Authentication System (`services/ory_auth.py`)

**OAuth2 Client Credentials Flow:**

```
1. Generate access token:
   ├─ Encode client_id:client_secret as Basic Auth
   ├─ POST to Ory Hydra /oauth2/token
   │   └─ grant_type=client_credentials
   └─ Cache token with expiration

2. Token caching:
   ├─ Store access_token + expires_at
   ├─ Refresh 60 seconds before expiry
   └─ Thread-safe with asyncio.Lock

3. Token usage:
   ├─ APIClient calls get_access_token()
   ├─ Adds "Authorization: Bearer {token}"
   └─ Auto-refresh on 401 errors
```

**Configuration:**
- `ORY_PROJECT_SLUG`: Ory Cloud project identifier
- `OAUTH2_CLIENT_ID`: M2M client ID
- `OAUTH2_CLIENT_SECRET`: M2M client secret
- `OAUTH2_SCOPE`: Requested scopes (default: "read write")

**Automatic Token Management:**
- Tokens cached until 60s before expiry
- 401 errors trigger immediate token refresh
- Metrics tracked for auth success/failure

---

### 6. Rate Limiting System (`services/rate_limiter.py`)

**Multi-Tier Architecture:**

#### Storage Strategy
- **In-Memory**: Minute/hour counters (performance)
- **SQLite Database**: Day/week/month counters (persistence)

#### Rate Limit Periods
```python
{
  MINUTE: 60 seconds,
  HOUR: 3600 seconds,
  DAY: 86400 seconds,
  WEEK: 604800 seconds,
  MONTH: 2592000 seconds (30 days)
}
```

#### Window Strategies

**Rolling Windows** (default):
- Counts tasks in last N seconds/minutes/hours
- Smooth rate limiting without traffic spikes at window boundaries
- Example: "100 tasks in last 60 minutes"

**Fixed Windows**:
- Calendar-based windows (minute: 00-59, day: 00:00-23:59)
- Simpler logic, but can have boundary effects
- Example: "100 tasks from 00:00 to 23:59 today"

#### Database Schema
```sql
-- Persistent counters for fixed windows
CREATE TABLE rate_limits (
  time_period TEXT PRIMARY KEY,
  current_count INTEGER,
  window_start TIMESTAMP,
  window_end TIMESTAMP,
  last_updated TIMESTAMP
);

-- Rolling window task history
CREATE TABLE task_completions (
  id INTEGER PRIMARY KEY,
  completed_at TIMESTAMP,
  task_type TEXT,
  task_id TEXT
);
```

#### Rate Limit Flow
```
check_all_limits(task_count):
  ├─ For each enabled period (minute/hour/day/week/month):
  │   ├─ Get current usage (memory or DB)
  │   ├─ Calculate window boundaries
  │   ├─ Check if usage + task_count > limit
  │   └─ Return denied if exceeded
  └─ Return allowed if all pass

record_completed_tasks(count):
  ├─ Update in-memory counters (minute/hour)
  ├─ Insert into task_completions (rolling windows)
  └─ Update rate_limits table (fixed windows)
```

**Configuration:**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STRATEGY=rolling  # or 'fixed'
RATE_LIMIT_PER_MINUTE=20
RATE_LIMIT_PER_HOUR=100
RATE_LIMIT_PER_DAY=500
RATE_LIMIT_PER_WEEK=2000
RATE_LIMIT_PER_MONTH=7500
```

---

### 7. Embedding Providers (`services/embedding_providers.py`)

**Provider Architecture:**

```
EmbeddingProviderFactory
  │
  ├─ OpenAI Mode ──────▶ OpenAIEmbeddingProvider
  │                       └─ Supports all OpenAI models
  │                       └─ Mock mode when API key = "your_openai_api_key_here"
  │
  ├─ Ollama Mode ──────▶ OllamaEmbeddingProvider
  │                       └─ Only supports models in SUPPORTED_MODELS config
  │                       └─ Auto-downloads missing models
  │
  └─ Hybrid Mode ──────▶ HybridEmbeddingProvider
                          ├─ Try Ollama first (if model supported)
                          └─ Fallback to OpenAI on failure
```

#### OpenAI Provider
- **Model Flexibility**: Accepts any model, lets OpenAI API validate
- **Mock Mode**: Generates random embeddings when `OPENAI_API_KEY=your_openai_api_key_here`
- **Token Tracking**: Reports actual token usage to metrics

#### Ollama Provider
- **Config-Driven**: Only processes models in `SUPPORTED_MODELS` list
- **Auto-Download**: Downloads models on-demand via `/api/pull`
- **Estimated Tokens**: Approximates token count (word-based)

#### Hybrid Provider
- **Smart Routing**: Ollama for supported models, OpenAI as fallback
- **Fault Tolerance**: Continues processing if Ollama fails
- **Cost Optimization**: Prefer free local Ollama when possible

**Configuration:**
```bash
PROCESSING_MODE=hybrid  # openai | ollama | hybrid
SUPPORTED_MODELS=["nomic-embed-text", "dengcao/Qwen3-Embedding-0.6B:Q8_0"]
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Data Flow

### End-to-End Task Processing Flow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Task Creation (External NestJS API)                       │
│    POST /api/ai-tasks                                         │
│    {                                                          │
│      type: "text_embedding",                                 │
│      content: { text: "...", model: "nomic-embed-text" },   │
│      state: "pending"                                        │
│    }                                                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Task Polling (TaskScheduler)                              │
│    Every 30s:                                                │
│    - GET /api/ai-tasks/pending?limit=10                      │
│    - Returns array of pending tasks                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Rate Limit Check (RateLimiter)                            │
│    - Check all configured limits (minute/hour/day/etc.)      │
│    - Allow if under limits                                   │
│    - Skip processing if exceeded (log warning)               │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Concurrency Control (Semaphore)                           │
│    - Acquire semaphore slot (CONCURRENCY_LIMIT=5)            │
│    - Process up to 5 tasks simultaneously                    │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Processor Selection (ProcessorFactory)                    │
│    - Match task.type to processor                            │
│    - Validate with can_process()                             │
│    - Return TextEmbeddingProcessor instance                  │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. Task Processing (TextEmbeddingProcessor)                  │
│    - Parse task.content → TextEmbeddingInput                 │
│    - Validate model support                                  │
│    - Call embedding_provider.create_embedding()              │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. AI Processing (EmbeddingProvider)                         │
│    Hybrid Mode:                                              │
│    ├─ Try Ollama: POST localhost:11434/api/embeddings       │
│    │   └─ Returns: { embedding: [...], model: "..." }       │
│    └─ Fallback OpenAI: POST api.openai.com/v1/embeddings    │
│        └─ Returns: { data: [{ embedding: [...] }] }         │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. Result Formatting (Processor)                             │
│    TaskResult {                                              │
│      task_id: "...",                                         │
│      status: "succeeded",                                    │
│      output_data: {                                          │
│        embedding: [0.123, -0.456, ...],                     │
│        model: "nomic-embed-text",                           │
│        usage: { prompt_tokens: 15, total_tokens: 15 }       │
│      }                                                        │
│    }                                                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 9. Status Update (APIClient)                                 │
│    PATCH /api/ai-tasks/:id                                   │
│    {                                                          │
│      state: "succeeded",                                     │
│      result: [0.123, -0.456, ...]  // Just the embedding    │
│    }                                                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 10. Rate Limit Recording (RateLimiter)                       │
│     - Increment in-memory counters (minute/hour)             │
│     - Insert into task_completions table                     │
│     - Update rate_limits table (day/week/month)              │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 11. Metrics Collection (Prometheus)                          │
│     - ai_tasks_processed_total{type=text_embedding}++        │
│     - ai_task_processing_duration_seconds.observe()          │
│     - openai_tokens_used_total{type=prompt_tokens}++         │
└──────────────────────────────────────────────────────────────┘
```

---

## Processing Modes

### Mode Comparison

| Feature | OpenAI | Ollama | Hybrid |
|---------|--------|--------|--------|
| **Cost** | Pay per token | Free (local) | Optimized |
| **Latency** | API call latency | Local (fast) | Depends on routing |
| **Models** | All OpenAI models | Config-defined only | Both |
| **Internet** | Required | Not required | Optional |
| **Fallback** | None | None | OpenAI backup |
| **Mock Mode** | ✅ (when API key = placeholder) | ❌ | ✅ (if OpenAI fallback) |

### Mode Selection Logic

```python
if PROCESSING_MODE == "openai":
    # Always use OpenAI (or mock if no API key)
    provider = OpenAIEmbeddingProvider()

elif PROCESSING_MODE == "ollama":
    # Always use local Ollama
    # Models must be in SUPPORTED_MODELS list
    provider = OllamaEmbeddingProvider()

elif PROCESSING_MODE == "hybrid":
    # Smart routing:
    if model in SUPPORTED_MODELS:
        try:
            return ollama_client.create_embedding()
        except:
            return openai_client.create_embedding()  # Fallback
    else:
        return openai_client.create_embedding()
```

### Mock Processing

When `OPENAI_API_KEY=your_openai_api_key_here` (placeholder value):
- OpenAI provider generates mock embeddings (1024 random floats)
- No actual API calls made
- Full end-to-end testing without costs
- Mock data marked in logs

---

## Authentication & Security

### OAuth2 Flow (Client Credentials)

```
AI Task Processor              Ory Hydra              NestJS API
     │                             │                      │
     │  1. Request token            │                      │
     │─────────────────────────────▶│                      │
     │  POST /oauth2/token          │                      │
     │  Authorization: Basic {b64}  │                      │
     │  grant_type=client_creds     │                      │
     │                               │                      │
     │  2. Return access token       │                      │
     │◀─────────────────────────────│                      │
     │  { access_token, expires_in } │                      │
     │                               │                      │
     │  3. Use token for API calls   │                      │
     │───────────────────────────────────────────────────▶│
     │  GET /api/ai-tasks/pending    │                      │
     │  Authorization: Bearer {token}│                      │
     │                               │                      │
     │  4. Token expires / 401       │                      │
     │◀───────────────────────────────────────────────────│
     │                               │                      │
     │  5. Refresh token             │                      │
     │─────────────────────────────▶│                      │
     │  (automatic retry)            │                      │
```

### Security Features

1. **Token Caching**: Tokens cached until 60s before expiry
2. **Automatic Refresh**: 401 errors trigger token refresh
3. **Thread Safety**: asyncio.Lock prevents race conditions
4. **Basic Auth**: Client credentials sent as HTTP Basic Auth
5. **Scope Control**: Configurable OAuth2 scopes

### NestJS API Integration

**Required M2M Guard Configuration:**
```typescript
// NestJS API must be configured with:
const hydraBasePath = this.configService.get<string>("ory.admin_url");
const introspectionToken = this.configService.get<string>("ory.access_token");
```

---

## Rate Limiting

### Multi-Tier Strategy

**Why Multi-Tier?**
- **Burst Protection**: Minute limits prevent sudden spikes
- **Sustained Control**: Hour/day limits control steady-state usage
- **Budget Management**: Week/month limits enforce long-term quotas
- **Flexible Policies**: Enable/disable tiers independently

### Example Configurations

#### 1. Burst Protection
```bash
RATE_LIMIT_PER_MINUTE=20   # Max 20 tasks/min
RATE_LIMIT_PER_HOUR=100    # Max 100 tasks/hr
RATE_LIMIT_PER_DAY=500     # Max 500 tasks/day
```
**Use Case:** Prevent API abuse, smooth out traffic

#### 2. Budget Control
```bash
RATE_LIMIT_PER_WEEK=2000   # Max 2000 tasks/week
RATE_LIMIT_PER_MONTH=7500  # Max 7500 tasks/month
RATE_LIMIT_STRATEGY=fixed  # Calendar-based windows
```
**Use Case:** Monthly billing cycles, predictable quotas

#### 3. Conservative Limits
```bash
RATE_LIMIT_PER_MINUTE=5    # Slow processing
RATE_LIMIT_PER_DAY=200     # Daily quota
```
**Use Case:** Free tier, development environment

### Rate Limit Exceeded Behavior

**Graceful Degradation:**
- Processing skipped (tasks remain pending)
- Warning logged with limit details
- Metrics incremented (`rate_limit_exceeded_total`)
- Service continues running (no crash)
- Next polling cycle may process if window reset

**No Queueing:**
- Exceeded tasks not queued
- Next poll will retry if limits reset
- Tasks remain in "pending" state in API

---

## Monitoring & Observability

### Structured Logging

**Library:** `structlog` with JSON output

**Log Levels:**
- **INFO**: Normal operations (task started/completed)
- **WARNING**: Retryable errors, rate limits exceeded
- **ERROR**: Non-retryable failures, unexpected errors

**Correlation IDs:**
- Every task gets `task_id` as correlation ID
- Enables request tracing across components
- Logs include: `task_id`, `task_type`, `processor`, `model`, etc.

**Example Log Entry:**
```json
{
  "event": "Task processing completed",
  "task_id": "64f3a2b1c8e9d...",
  "task_type": "text_embedding",
  "status": "succeeded",
  "processor": "TextEmbeddingProcessor",
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "info"
}
```

### Prometheus Metrics

#### Task Metrics
```prometheus
# Total tasks processed
ai_tasks_processed_total{task_type="text_embedding", status="succeeded"}

# Processing duration histogram
ai_task_processing_duration_seconds{task_type="text_embedding"}

# Tasks currently processing
ai_tasks_in_flight
```

#### API Metrics
```prometheus
# API request counts
api_requests_total{endpoint="/api/ai-tasks/pending", method="GET", status_code="200"}

# API request duration
api_request_duration_seconds{endpoint="/api/ai-tasks/pending", method="GET"}
```

#### AI Provider Metrics
```prometheus
# OpenAI requests
openai_requests_total{model="text-embedding-3-small", status="success"}
openai_tokens_used_total{model="text-embedding-3-small", type="prompt_tokens"}

# Ollama requests
ollama_requests_total{model="nomic-embed-text", status="success"}
ollama_tokens_used_total{model="nomic-embed-text", type="prompt_tokens"}
```

#### Rate Limiting Metrics
```prometheus
# Current usage per period
rate_limit_current_usage{period="minute"}
rate_limit_current_usage{period="day"}

# Configured limits
rate_limit_max_allowed{period="minute"}

# Remaining quota
rate_limit_remaining{period="minute"}

# Exceeded events
rate_limit_exceeded_total{period="day"}
```

#### Circuit Breaker Metrics
```prometheus
# Circuit breaker state (0=closed, 1=open, 2=half-open)
circuit_breaker_state{service="api"}
```

### Health Endpoints

#### `/health` - Liveness Probe
```json
{
  "status": "healthy",
  "service": "ai-task-processor",
  "rate_limiting": {
    "enabled": true,
    "strategy": "rolling",
    "current_usage": {
      "minute": { "current": 15, "limit": 20, "remaining": 5 },
      "hour": { "current": 87, "limit": 100, "remaining": 13 },
      "day": { "current": 342, "limit": 500, "remaining": 158 }
    }
  }
}
```

#### `/ready` - Readiness Probe
```json
{
  "status": "ready",
  "service": "ai-task-processor"
}
```

#### `/metrics` - Prometheus Scrape Endpoint
Raw Prometheus metrics in text format

---

## Error Handling & Resilience

### Three-Tier Error Classification

```python
# 1. RetryableError - Temporary failures
RetryableError:
  - 5xx server errors
  - Network timeouts
  - Connection errors
  - 401 auth errors (token refresh)
  - Rate limit errors (429)

# 2. NonRetryableError - Permanent failures
NonRetryableError:
  - 4xx client errors (except 401)
  - Invalid input data
  - Unsupported models
  - Authentication failures

# 3. Generic Exception - Catch-all
Exception:
  - Unexpected errors
  - Logged with full stack trace
  - Treated as non-retryable
```

### Retry Strategy

**Exponential Backoff with Jitter:**
```python
@retry(
    retryable_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
    non_retryable_exceptions=(NonRetryableError,)
)
async def _make_request():
    # Retry logic:
    # - Max retries: 3 (configurable via MAX_RETRIES)
    # - Backoff factor: 2.0 (configurable via RETRY_BACKOFF_FACTOR)
    # - Delays: 2s, 4s, 8s (with random jitter)
```

**Retry Locations:**
- API client requests
- OpenAI embedding calls
- Ollama embedding calls
- Ollama model downloads

### Circuit Breaker Pattern

**Purpose:** Prevent cascading failures when NestJS API is down

**States:**
```
CLOSED (Normal):
  ├─ Requests flow through
  └─ Failures < threshold (default: 5)

OPEN (Failing):
  ├─ Requests blocked immediately
  ├─ Triggered after 5 consecutive failures
  └─ Wait 60s for recovery timeout

HALF-OPEN (Testing):
  ├─ After 60s recovery timeout
  ├─ Allow 1 test request
  ├─ Success → Reset to CLOSED
  └─ Failure → Back to OPEN
```

**Metrics:** `circuit_breaker_state{service="api"}` (0/1/2)

### Graceful Shutdown

**Shutdown Flow:**
```python
1. Receive SIGTERM/SIGINT signal
   ├─ Set shutdown_requested flag
   └─ Log shutdown initiation

2. Stop accepting new tasks
   ├─ TaskScheduler stops polling
   └─ New task polling skipped

3. Wait for in-flight tasks
   ├─ Track active tasks in shutdown_manager
   ├─ Wait for asyncio tasks to complete
   └─ Max wait: 30 seconds (configurable)

4. Cleanup resources
   ├─ Close HTTP clients
   ├─ Flush metrics
   ├─ Close database connections
   └─ Stop metrics server

5. Exit cleanly
   └─ Log shutdown complete
```

**Implementation:**
- `shutdown_manager.setup_signal_handlers()` catches signals
- `shutdown_manager.add_task()` tracks in-flight tasks
- `shutdown_manager.wait_for_shutdown()` blocks until clean exit

---

## Deployment Architecture

### Docker Compose Stack

```yaml
services:
  ai-task-processor:
    # Main service
    ports:
      - "8001:8001"  # Metrics endpoint
    volumes:
      - ./data:/app/data  # Rate limit DB persistence
    environment:
      - API_BASE_URL=http://nestjs-api:3000
      - PROCESSING_MODE=hybrid
      - RATE_LIMIT_ENABLED=true

  ollama:
    # Local LLM server
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

  prometheus:
    # Metrics collection
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    # Metrics visualization
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
```

### Network Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Docker Network                      │
│                                                          │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │  ai-task-       │         │  ollama          │     │
│  │  processor:8001 │────────▶│  :11434          │     │
│  └────────┬─────────┘         └──────────────────┘     │
│           │                                              │
│           │ ┌──────────────────────────┐                │
│           ├▶│ prometheus:9090          │                │
│           │ └──────────────────────────┘                │
│           │                                              │
│           │ ┌──────────────────────────┐                │
│           └▶│ grafana:3001             │                │
│             └──────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
          ┌─────────────────────────┐
          │   External Services     │
          ├─────────────────────────┤
          │ • NestJS API (external) │
          │ • OpenAI API (internet) │
          │ • Ory Cloud (internet)  │
          └─────────────────────────┘
```

### Volume Persistence

```
./data/rate_limits.db      # Rate limiting state (survives restarts)
ollama_data:/root/.ollama  # Downloaded Ollama models
grafana_data:/var/lib/...  # Grafana dashboards/config
```

### Configuration Files

```
.env                  # Environment variables (secrets)
.env.example          # Template for configuration
docker-compose.yml    # Service orchestration
prometheus.yml        # Prometheus scrape config
requirements.txt      # Python dependencies
```

### Startup Sequence

```
1. docker-compose up -d ollama
   └─ Ollama starts, ready to download models

2. docker-compose up -d prometheus grafana
   └─ Monitoring stack starts

3. docker-compose up -d ai-task-processor
   ├─ Load configuration from .env
   ├─ Initialize rate limiter DB
   ├─ Download Ollama models (if PROCESSING_MODE=ollama/hybrid)
   ├─ Start task scheduler
   ├─ Start metrics server
   └─ Begin polling for tasks
```

---

## Component Interaction Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                       TaskScheduler                             │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Polling Loop (every 30s)                                  │ │
│  └──────┬───────────────────────────────────────────────────┘ │
└─────────┼──────────────────────────────────────────────────────┘
          │
          ▼
    ┌─────────────┐
    │ RateLimiter │◀──────────────────┐
    └──────┬──────┘                   │
           │ allowed?                 │
           ▼                           │
    ┌──────────────┐                  │
    │  APIClient   │                  │
    │  (+ Circuit  │                  │
    │   Breaker)   │                  │
    └──────┬───────┘                  │
           │                           │
           ▼                           │
    ┌──────────────┐                  │
    │  OryAuth     │                  │
    │  (OAuth2)    │                  │
    └──────┬───────┘                  │
           │ Bearer token             │
           ▼                           │
    ┌───────────────────────┐         │
    │ NestJS API            │         │
    │ GET /ai-tasks/pending │         │
    └───────┬───────────────┘         │
            │                          │
            ▼                          │
    ┌──────────────────┐              │
    │ ProcessorFactory │              │
    └────────┬─────────┘              │
             │                         │
   ┌─────────┴─────────┐              │
   ▼                   ▼              │
┌──────────┐    ┌─────────────┐      │
│ Text     │    │ Identifying │      │
│ Embedding│    │ Data        │      │
│ Processor│    │ Processor   │      │
└────┬─────┘    └──────┬──────┘      │
     │                 │              │
     ▼                 ▼              │
┌────────────────────────────┐       │
│  EmbeddingProviderFactory  │       │
│  ┌──────────────────────┐  │       │
│  │ OpenAI/Ollama/Hybrid │  │       │
│  └──────────────────────┘  │       │
└──────────┬─────────────────┘       │
           │                          │
           ▼                          │
     AI Processing                    │
     (embeddings)                     │
           │                          │
           ▼                          │
    ┌──────────────┐                 │
    │ TaskResult   │                 │
    └──────┬───────┘                 │
           │                          │
           ▼                          │
    ┌──────────────┐                 │
    │ APIClient    │                 │
    │ PATCH /tasks │                 │
    └──────┬───────┘                 │
           │                          │
           ▼                          │
    ┌──────────────┐                 │
    │ RateLimiter  │─────────────────┘
    │ record_tasks │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Metrics      │
    │ (Prometheus) │
    └──────────────┘
```

---

## Extension Points

### Adding New Task Types

**Steps:**
1. Add enum to `models/task.py`:
   ```python
   class TaskType(str, Enum):
       NEW_TYPE = "new_type"
   ```

2. Create input/output models:
   ```python
   class NewTypeInput(BaseModel):
       data: str
   ```

3. Create processor in `processors/new_type.py`:
   ```python
   class NewTypeProcessor(BaseProcessor):
       def can_process(self, task): ...
       async def process(self, task): ...
   ```

4. Register in `processors/factory.py`:
   ```python
   TaskType.NEW_TYPE: NewTypeProcessor()
   ```

### Adding New AI Providers

**Steps:**
1. Create client in `services/new_provider.py`
2. Implement retry logic + metrics
3. Add provider to `embedding_providers.py`
4. Update configuration in `config/settings.py`
5. Add to `ProcessingMode` enum

### Adding New Metrics

```python
# In services/metrics.py
new_metric = Counter(
    'new_metric_total',
    'Description',
    ['label1', 'label2']
)

class MetricsCollector:
    def record_new_metric(self, label1, label2):
        new_metric.labels(label1=label1, label2=label2).inc()
```

---

## Configuration Reference

### Required Environment Variables

```bash
# API Integration
API_BASE_URL=http://nestjs-api:3000

# OAuth2 Authentication
ORY_PROJECT_SLUG=your-project-slug
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_SCOPE="read write"

# AI Processing (optional for mock mode)
OPENAI_API_KEY=your_openai_api_key_here
```

### Optional Configuration

```bash
# Polling & Concurrency
POLLING_INTERVAL_SECONDS=30
CONCURRENCY_LIMIT=5

# Processing Mode
PROCESSING_MODE=hybrid  # openai | ollama | hybrid
SUPPORTED_MODELS=["nomic-embed-text"]

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=120
OLLAMA_MODEL_DOWNLOAD_TIMEOUT=600

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STRATEGY=rolling  # rolling | fixed
RATE_LIMIT_PER_MINUTE=20
RATE_LIMIT_PER_HOUR=100
RATE_LIMIT_PER_DAY=500
RATE_LIMIT_PER_WEEK=2000
RATE_LIMIT_PER_MONTH=7500
RATE_LIMIT_STORAGE_PATH=/app/data/rate_limits.db

# Resilience
MAX_RETRIES=3
RETRY_BACKOFF_FACTOR=2.0
CIRCUIT_BREAKER_THRESHOLD=5
REQUEST_TIMEOUT=30
OPENAI_TIMEOUT=60

# Monitoring
METRICS_PORT=8001
LOG_LEVEL=INFO
```

---

## Troubleshooting Guide

### Common Issues

**1. Rate Limits Exceeded**
```
Symptom: "Rate limit exceeded, skipping task processing"
Cause: Too many tasks processed in time window
Solution:
  - Increase limits in .env (RATE_LIMIT_PER_*)
  - Or switch to rolling strategy
  - Or disable: RATE_LIMIT_ENABLED=false
```

**2. Circuit Breaker Open**
```
Symptom: "Circuit breaker is open"
Cause: 5+ consecutive API failures
Solution:
  - Check API_BASE_URL is correct
  - Verify NestJS API is running
  - Check OAuth2 credentials
  - Wait 60s for auto-recovery
```

**3. OAuth2 Token Failures**
```
Symptom: "Authentication failed: 401"
Cause: Invalid credentials or expired token
Solution:
  - Verify ORY_PROJECT_SLUG is correct
  - Check OAUTH2_CLIENT_ID/SECRET
  - Ensure client has correct grant_types
  - Check Ory Cloud console for client config
```

**4. Ollama Model Not Found**
```
Symptom: "Model not found: 404"
Cause: Model not downloaded or wrong name
Solution:
  - Check SUPPORTED_MODELS list
  - Ensure Ollama is running
  - Manually pull: docker exec ollama ollama pull nomic-embed-text
```

**5. Tasks Not Processing**
```
Symptom: No tasks being processed
Debug:
  - Check /health endpoint for rate limiting status
  - Verify API returns tasks: curl API_BASE_URL/api/ai-tasks/pending
  - Check logs for errors
  - Verify CONCURRENCY_LIMIT > 0
```

---

## Performance Considerations

### Throughput Limits

**Bottlenecks:**
1. **Concurrency Limit**: Max simultaneous tasks (default: 5)
2. **Rate Limits**: Per-period quotas
3. **API Latency**: NestJS API response time
4. **AI Provider**: OpenAI rate limits, Ollama processing speed

**Max Throughput:**
```
Best case (no rate limits):
  = (CONCURRENCY_LIMIT / avg_task_duration) * 60 tasks/minute

Example (5 concurrent, 2s avg):
  = (5 / 2) * 60 = 150 tasks/minute

Real case (with rate limits):
  = MIN(calculated_throughput, RATE_LIMIT_PER_MINUTE)
```

### Optimization Strategies

**1. Increase Concurrency:**
```bash
CONCURRENCY_LIMIT=10  # More simultaneous tasks
```

**2. Reduce Polling Interval:**
```bash
POLLING_INTERVAL_SECONDS=10  # Poll more frequently
```

**3. Use Ollama for Speed:**
```bash
PROCESSING_MODE=ollama  # Local processing, no API latency
```

**4. Batch Processing:**
```bash
# Fetch more tasks per poll
# Scheduler fetches CONCURRENCY_LIMIT * 2
```

### Resource Requirements

**Minimum:**
- CPU: 1 core
- RAM: 512MB
- Disk: 100MB (without Ollama)

**Recommended:**
- CPU: 2 cores
- RAM: 2GB
- Disk: 10GB (with Ollama models)

**Ollama Models:**
- `nomic-embed-text`: ~274MB
- `dengcao/Qwen3-Embedding-0.6B:Q8_0`: ~600MB

---

## Security Best Practices

### 1. Secrets Management
```bash
# Never commit .env to git
echo ".env" >> .gitignore

# Use environment-specific files
.env.development
.env.staging
.env.production
```

### 2. OAuth2 Client Configuration
```
- Use strong client secrets (32+ characters)
- Rotate credentials regularly
- Use minimal scopes (principle of least privilege)
- Monitor token usage via Ory Cloud console
```

### 3. Network Security
```yaml
# docker-compose.yml
services:
  ai-task-processor:
    networks:
      - internal  # Only internal services
      - external  # Only when needed
```

### 4. Rate Limiting as DDoS Protection
```
Enable rate limiting in production to prevent:
- Accidental infinite loops
- Malicious task flooding
- API quota exhaustion
```

---

## Appendix: API Contract

### Task Object (from NestJS API)
```typescript
interface Task {
  _id: string;
  type: "text_embedding" | "identifying_data";
  state: "pending" | "in_progress" | "succeeded" | "failed";
  content: string | { text: string, model?: string };
  callbackRoute: string;
  callbackParams: { targetId: string, field: string };
  createdAt: Date;
  updatedAt?: Date;
}
```

### Update Request (to NestJS API)
```typescript
PATCH /api/ai-tasks/:id
{
  state: "succeeded" | "failed",
  result: number[] | null  // Embedding array or null
}
```

### Callback Routes
```typescript
enum CallbackRoute {
  VERIFICATION_UPDATE_EMBEDDING = "verification_update_embedding",
  VERIFICATION_UPDATE_IDENTIFYING_DATA = "verification_update_identifying_data"
}
```

---

## Version History

- **v1.0.0** (2025-01-15): Initial architecture documentation
  - Core task processing pipeline
  - Multi-tier rate limiting
  - OAuth2 authentication
  - Hybrid OpenAI/Ollama support
  - Comprehensive monitoring

---

**Document Status:** Living documentation - update as architecture evolves
**Last Updated:** 2025-01-15
**Maintainer:** Development Team