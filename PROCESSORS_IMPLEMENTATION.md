# New Processors Implementation Summary

This document describes the implementation of three new AI task processors that follow the same architecture pattern as the `identifying_data` processor.

## Overview

All three new processors follow the same architecture:
1. **OpenAI-based AI Analysis** - Uses OpenAI models to analyze text
2. **Wikidata Enrichment** - Enriches results with Wikidata information
3. **Graceful Error Handling** - Failures in enrichment don't break the task
4. **Structured Logging** - Comprehensive logging with correlation IDs
5. **Retry Logic** - Automatic retries for transient failures

---

## 1. Defining Topics Processor

### Purpose
Identifies main topics discussed in a given text.

### Task Type
`DEFINING_TOPICS`

### Callback Route
`VERIFICATION_UPDATE_DEFINING_TOPICS`

### Input Model
```python
class DefiningTopicsInput(BaseModel):
    text: str
    model: str = "o3-mini"
```

### Output Model
```python
class Topic(BaseModel):
    name: str  # Topic name
    confidence: float  # Confidence score (0-1)
    context: str  # Context of the topic
    wikidata: Optional[WikidataEntity] = None

class DefiningTopicsOutput(BaseModel):
    topics: List[Topic]
    model: str
    usage: Dict[str, int]
```

### Example Output
```json
{
  "topics": [
    {
      "name": "Politics",
      "confidence": 0.95,
      "context": "The text discusses political matters",
      "wikidata": {
        "id": "Q7163",
        "url": "https://www.wikidata.org/wiki/Q7163",
        "label": "Politics",
        "description": "theory and practice of organizing society",
        "aliases": ["political science", "government"]
      }
    }
  ],
  "model": "o3-mini",
  "usage": {"prompt_tokens": 50, "total_tokens": 50}
}
```

### AI Prompt
The OpenAI model receives a prompt asking it to:
- Identify main topics in the text
- Provide confidence scores
- Include context for each topic
- Return structured JSON

### Wikidata Enrichment
- Each topic name is searched in Wikidata
- Best match is selected based on Wikidata ranking
- Adds entity ID, label, description, and aliases

### Files
- **Service**: `ai_task_processor/services/defining_services.py` (`DefiningTopicsProvider`)
- **Processor**: `ai_task_processor/processors/defining_topics.py`
- **Models**: `ai_task_processor/models/task.py` (`DefiningTopicsInput`, `Topic`, `DefiningTopicsOutput`)

---

## 2. Defining Impact Area Processor

### Purpose
Identifies the areas of impact discussed or implied in a given text.

### Task Type
`DEFINING_IMPACT_AREA`

### Callback Route
`VERIFICATION_UPDATE_DEFINING_IMPACT_AREA`

### Input Model
```python
class DefiningImpactAreaInput(BaseModel):
    text: str
    model: str = "o3-mini"
    options: List[str] = []  # closed list of impact area names sent by the backend
```

### Output
The task result sent in the callback:
```json
{
  "name": "Saúde",
  "description": "",
  "wikidataId": "Q12147",
  "language": "pt"
}
```

### Model Routing
- **Jev** (`model` starts with `jev`, e.g. `jev-1.13.0`): one choice question over
  `options`, with the VR text only. Requires `options`. `description` is empty.
- **OpenAI** (any other model): prompt asking for the primary impact area as JSON. When
  `options` are sent, the name must be exactly one of them.
- Temporary Jev errors fall back to OpenAI with a daily cap. See [docs/JEV_TRIAGE.md](docs/JEV_TRIAGE.md).

### Wikidata Enrichment
- Each impact area name is searched in Wikidata
- Enriches with entity information
- Helps standardize impact area classifications

### Files
- **Service**: `ai_task_processor/services/defining_services.py` (`DefiningImpactAreaProvider`)
- **Jev**: `ai_task_processor/services/jev_client.py`, `jev_rubric.py`, `jev_fallback.py`
- **Processor**: `ai_task_processor/processors/defining_impact_area.py`
- **Models**: `ai_task_processor/models/task.py` (`DefiningImpactAreaInput`, `ImpactArea`, `DefiningImpactAreaOutput`)

---

## 3. Defining Severity Processor

### Purpose
Assesses the severity level of issues, events, or situations described in text.

### Task Type
`DEFINING_SEVERITY`

### Callback Route
`VERIFICATION_UPDATE_DEFINING_SEVERITY`

### Input Model
```python
class DefiningSeverityInput(BaseModel):
    impactArea: Optional[SeverityImpactArea] = None  # name, language, wikidataId
    topics: List[SeverityTopic] = []                 # name, language, wikidataId
    personalities: List[SeverityPersonality] = []    # name, wikidataId
    text: str
    model: str = "o3-mini"
```

### Output
The task result sent in the callback is one `SeverityEnum` value:
```json
{ "severity": "high_2" }
```

### Severity Scale
`low_1`, `low_2`, `low_3`, `medium_1`, `medium_2`, `medium_3`, `high_1`, `high_2`, `high_3`, `critical`

### Model Routing
- **Jev** (`model` starts with `jev`, e.g. `jev-1.13.0`): Jev answers harm, contestable and
  checkable about the VR text only; the fixed rubric in `services/jev_rubric.py` turns the
  answers and the personalities' reach into the severity.
- **OpenAI** (any other model): reasoning prompt with the text and the Wikidata context of the
  impact area, topics and personalities.
- Temporary Jev errors fall back to OpenAI with a daily cap. See [docs/JEV_TRIAGE.md](docs/JEV_TRIAGE.md).

### Wikidata Enrichment
- Fetches Wikidata data for the impact area, topics and personalities (sitelinks, pageviews,
  followers, positions held)
- Feeds the OpenAI prompt and, on Jev, the reach matrix

### Files
- **Service**: `ai_task_processor/services/defining_services.py` (`DefiningSeverityProvider`)
- **Jev**: `ai_task_processor/services/jev_client.py`, `jev_rubric.py`, `jev_fallback.py`
- **Processor**: `ai_task_processor/processors/defining_severity.py`
- **Models**: `ai_task_processor/models/task.py` (`DefiningSeverityInput`, `Severity`, `DefiningSeverityOutput`)

---

## Architecture Patterns

### 1. Provider Pattern
Each processor uses a dedicated provider class that handles:
- AI model interaction (OpenAI)
- Mock mode support (when API key is placeholder)
- Error handling and logging

### 2. Wikidata Enrichment Pattern
All processors use the same enrichment approach:
```python
async def _enrich_with_wikidata(items, correlation_id):
    enriched_items = []
    for item in items:
        enriched = item.copy()
        wikidata_info = await wikidata_client.enrich_personality(
            name=item["name"],
            mentioned_as=item["name"],
            language="en",
            correlation_id=correlation_id
        )
        enriched["wikidata"] = wikidata_info
        enriched_items.append(enriched)
    return enriched_items
```

### 3. Error Handling
- **Retryable Errors**: Network issues, timeouts, 5xx errors
- **Non-Retryable Errors**: Invalid input, 4xx errors, unsupported models
- **Graceful Degradation**: Wikidata enrichment failures don't fail the task

### 4. Mock Mode
When `OPENAI_API_KEY=your_openai_api_key_here`:
- Generates realistic mock data
- Allows full end-to-end testing
- No API costs

When `TYPESAFE_API_KEY=your_typesafe_api_key_here`, tasks routed to Jev get mock Jev answers
in the real format, so the rubric and callbacks run for real.

---

## Integration with NestJS API

### Task Creation Format
```typescript
POST /api/ai-tasks
{
  "type": "defining_topics",  // or "defining_impact_area", "defining_severity"
  "content": {
    "text": "Your text to analyze",
    "model": "o3-mini"
  },
  "state": "pending",
  "callbackRoute": "verification_update_defining_topics",
  "callbackParams": {
    "targetId": "64f3a2b1c8e9d...",
    "field": "topics"
  }
}
```

### Task Update Format
```typescript
PATCH /api/ai-tasks/:id
{
  "state": "succeeded",
  "result": {
    "topics": [...],  // or "impact_areas", "severity"
    "model": "o3-mini",
    "usage": {...}
  }
}
```

---

## Monitoring & Observability

### Metrics
All processors emit standard Prometheus metrics:
```prometheus
# Task processing metrics
ai_tasks_processed_total{task_type="defining_topics", status="succeeded"}
ai_task_processing_duration_seconds{task_type="defining_topics"}

# OpenAI usage
openai_requests_total{model="o3-mini", status="success"}
openai_tokens_used_total{model="o3-mini", type="prompt_tokens"}

# Jev usage and the provider that resolved each Jev-routed task
jev_requests_total{model="jev-1.13.0", status="success"}
triage_provider_total{task_type="defining_severity", provider="jev"}
```

### Logs
Structured logs with correlation IDs:
```json
{
  "event": "Wikidata enrichment completed",
  "task_id": "64f3a2b1...",
  "task_type": "defining_topics",
  "total_topics": 5,
  "enriched_count": 4,
  "correlation_id": "64f3a2b1...",
  "level": "info"
}
```

---

## Configuration

### Environment Variables
```bash
# AI Processing
OPENAI_API_KEY=your_api_key_here
PROCESSING_MODE=openai

# Jev (impact area and severity tasks with a "jev-*" model)
TYPESAFE_API_KEY=your_typesafe_api_key_here
JEV_FALLBACK_MODEL=o3
JEV_FALLBACK_MAX_PER_DAY=50

# Models (if using different models)
SUPPORTED_MODELS=["o3-mini", "gpt-4"]

# Rate Limiting (shared across all processors)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=20
```

---

## Testing

### Mock Mode Testing
All three processors support mock mode for testing:
```bash
# Set placeholder API key
export OPENAI_API_KEY="your_openai_api_key_here"

# Processors will return realistic mock data
# - Topics: Politics, Economy
# - Impact Area: the first of content.options ("Social Impact" without options)
# - Severity: medium_2

# Set the Jev placeholder key for mock Jev answers (impact area and severity with a "jev-*" model)
export TYPESAFE_API_KEY="your_typesafe_api_key_here"
```

### Integration Testing
Create test tasks via NestJS API and verify:
1. Task is picked up by processor
2. AI analysis completes successfully
3. Wikidata enrichment adds entity information
4. Task status updated to "succeeded"
5. Metrics are recorded

---

## Files Created/Modified

### New Files
1. `ai_task_processor/services/defining_services.py` - AI providers for all three tasks
2. `ai_task_processor/processors/defining_topics.py` - Topics processor
3. `ai_task_processor/processors/defining_impact_area.py` - Impact area processor
4. `ai_task_processor/processors/defining_severity.py` - Severity processor

### Modified Files
1. `ai_task_processor/models/task.py` - Added new input/output models
2. `ai_task_processor/processors/factory.py` - Registered new processors
3. `ai_task_processor/services/__init__.py` - Exported new services

---

## Future Enhancements

### 1. Configurable Language
Currently hardcoded to English ("en"). Could be made configurable:
```python
language = settings.wikidata_language  # Default: "en"
```

### 2. Batch Wikidata Enrichment
Currently enriches items sequentially. Could optimize with batch API calls:
```python
await wikidata_client.batch_enrich_items(items)
```

### 3. Caching
Cache Wikidata results to reduce API calls:
```python
@cache(ttl=3600)
async def enrich_personality(name: str):
    ...
```

### 4. Alternative AI Providers
Support for Ollama or other local LLMs:
```python
if settings.processing_mode == ProcessingMode.OLLAMA:
    provider = OllamaDefiningTopicsProvider()
```

---

## Summary

All three processors are now fully implemented and follow the same architecture:

✅ **Defining Topics** - Identifies main topics with Wikidata enrichment
✅ **Defining Impact Area** - Identifies impact areas with Wikidata enrichment
✅ **Defining Severity** - Assesses severity levels with Wikidata enrichment

Each processor:
- Uses OpenAI for AI analysis
- Enriches results with Wikidata
- Supports mock mode for testing
- Includes comprehensive error handling
- Provides structured logging and metrics
- Is registered in the ProcessorFactory

The implementation is production-ready and consistent with the existing codebase architecture.
