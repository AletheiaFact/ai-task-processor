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
```

### Output Model
```python
class ImpactArea(BaseModel):
    name: str  # Impact area name
    description: str  # Description of the impact
    confidence: float  # Confidence score (0-1)
    wikidata: Optional[WikidataEntity] = None

class DefiningImpactAreaOutput(BaseModel):
    impact_areas: List[ImpactArea]
    model: str
    usage: Dict[str, int]
```

### Example Output
```json
{
  "impact_areas": [
    {
      "name": "Social Impact",
      "description": "Affects social structures and relationships",
      "confidence": 0.90,
      "wikidata": {
        "id": "Q8425",
        "url": "https://www.wikidata.org/wiki/Q8425",
        "label": "society",
        "description": "group of individuals living together in organized communities",
        "aliases": ["social", "societal"]
      }
    },
    {
      "name": "Economic Impact",
      "description": "Influences economic conditions and markets",
      "confidence": 0.85,
      "wikidata": {
        "id": "Q8134",
        "url": "https://www.wikidata.org/wiki/Q8134",
        "label": "economics",
        "description": "social science of resource allocation",
        "aliases": ["economic science"]
      }
    }
  ],
  "model": "o3-mini",
  "usage": {"prompt_tokens": 50, "total_tokens": 50}
}
```

### AI Prompt
The OpenAI model receives a prompt asking it to:
- Identify main impact areas
- Describe each impact
- Provide confidence scores
- Return structured JSON

### Wikidata Enrichment
- Each impact area name is searched in Wikidata
- Enriches with entity information
- Helps standardize impact area classifications

### Files
- **Service**: `ai_task_processor/services/defining_services.py` (`DefiningImpactAreaProvider`)
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
    text: str
    model: str = "o3-mini"
```

### Output Model
```python
class Severity(BaseModel):
    level: str  # "low", "medium", "high", "critical"
    score: float  # Numerical score (0-10)
    reasoning: str  # Explanation
    factors: List[str]  # Contributing factors
    wikidata: Optional[WikidataEntity] = None

class DefiningSeverityOutput(BaseModel):
    severity: Severity
    model: str
    usage: Dict[str, int]
```

### Example Output
```json
{
  "severity": {
    "level": "high",
    "score": 7.2,
    "reasoning": "The text describes serious political tensions with potential for escalation",
    "factors": [
      "Political instability",
      "Economic crisis",
      "Social unrest",
      "International pressure"
    ],
    "wikidata": {
      "id": "Q6527775",
      "url": "https://www.wikidata.org/wiki/Q6527775",
      "label": "severity",
      "description": "extent of harm or damage",
      "aliases": ["seriousness", "gravity"]
    }
  },
  "model": "o3-mini",
  "usage": {"prompt_tokens": 50, "total_tokens": 50}
}
```

### Severity Scale
- **low (0-2.5)**: Minor issues with limited impact
- **medium (2.5-5)**: Moderate issues requiring attention
- **high (5-7.5)**: Serious issues with significant impact
- **critical (7.5-10)**: Severe issues requiring immediate action

### AI Prompt
The OpenAI model receives a prompt asking it to:
- Assess severity level (low/medium/high/critical)
- Provide numerical score (0-10)
- Explain the reasoning
- List key contributing factors
- Return structured JSON

### Wikidata Enrichment
- Searches for severity classification concepts
- Enriches with standardized definitions
- Helps maintain consistency across assessments

### Files
- **Service**: `ai_task_processor/services/defining_services.py` (`DefiningSeverityProvider`)
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
PROCESSING_MODE=openai  # Only OpenAI supported for these tasks

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
# - Impact Areas: Social Impact, Economic Impact
# - Severity: medium level with mock factors
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
