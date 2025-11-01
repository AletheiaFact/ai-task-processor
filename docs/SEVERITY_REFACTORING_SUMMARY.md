# Severity Processing Refactoring Summary

## Overview
Refactored the severity definition system to use AI-powered reasoning instead of hardcoded weights, following the established service pattern used in other processors.

---

## Key Changes

### 1. **AI-Powered Reasoning Instead of Mathematical Scoring**

**Before:**
- Hardcoded weights: 30% personality, 40% impact, 30% topics
- Manual scoring calculations with predefined impact area priorities
- Numeric score → enum mapping

**After:**
- OpenAI analyzes rich Wikidata context holistically
- No hardcoded weights or priorities
- Direct classification to SeverityEnum

### 2. **Rich Wikidata Context Enrichment**

**New Fields Added:**
- `sitelinks`: Global recognition/reach
- `statements`: Data completeness
- `inbound_links`: Centrality in knowledge graph (via SPARQL)
- `pageviews`: 30-day public engagement (via Wikipedia API)
- `description`: Qualitative context
- `instance_of`: Entity classification

**Applied to:**
- Personality data
- Topic data
- Impact area data

### 3. **Service Pattern Adoption**

**Created:** `ai_task_processor/services/defining_severity.py`

Follows the same pattern as:
- `identifying_data.py`
- `defining_services.py` (topics/impact area)
- `embedding_providers.py`

**Key Methods:**
- `supports_model()`: Model validation
- `define_severity()`: Main classification logic
- `_build_severity_prompt()`: Structured prompt generation
- `_classify_severity_with_ai()`: OpenAI API interaction

### 4. **Dynamic Model Selection**

**Updated:** `DefiningSeverityInput` model

```python
class DefiningSeverityInput(BaseModel):
    verificationId: str
    impactAreaWikidataId: str
    topicsWikidataIds: List[str]
    personalityWikidataId: Optional[str] = None
    contentSummary: str
    model: str = "gpt-4o-mini"  # ← Configurable model
```

**Task Content Example:**
```json
{
  "verificationId": "vr_123",
  "impactAreaWikidataId": "Q8068",
  "topicsWikidataIds": ["Q7942", "Q12739"],
  "personalityWikidataId": "Q22571744",
  "contentSummary": "Statement about climate action",
  "model": "gpt-4o-mini"
}
```

---

## Architecture Comparison

### Old Architecture
```
NestJS → Python Processor
         ├── wikidata_enrichment (basic data)
         ├── Calculate scores (personality, impact, topics)
         ├── Apply hardcoded weights
         └── Map numeric score → enum
```

### New Architecture
```
NestJS → Python Processor → defining_severity service
         ├── wikidata_enrichment (rich context)
         │   ├── sitelinks, statements
         │   ├── inbound_links (SPARQL)
         │   └── pageviews (Wikipedia API)
         ├── Build AI prompt with context
         └── OpenAI reasoning → direct enum
```

---

## Files Modified

### Services
- ✅ **Created:** `ai_task_processor/services/defining_severity.py`
- ✅ **Updated:** `ai_task_processor/services/wikidata_enrichment.py`
  - Removed: `IMPACT_AREA_PRIORITIES` dictionary
  - Removed: Scoring functions (`_calculate_*`)
  - Added: `_get_inbound_links_count()` with SPARQL
  - Added: `_get_wikipedia_pageviews()` with Wikipedia API
  - Updated: All enrichment functions to return rich context

### Processors
- ✅ **Updated:** `ai_task_processor/processors/defining_severity.py`
  - Follows standard processor pattern
  - Validates input with `DefiningSeverityInput`
  - Extracts model from `task.content`
  - Uses `defining_severity` service
  - Removed internal prompt/classification methods

### Models
- ✅ **Updated:** `ai_task_processor/models/task.py`
  - Updated `DefiningSeverityInput` with proper fields
  - Added `model` parameter for dynamic selection

### Tests
- ✅ **Updated:** `test_severity_processor.py`
  - Added `model` parameter to all test cases

### Documentation
- ✅ **Created:** `docs/SEVERITY_REFACTORING_SUMMARY.md` (this file)

---

## Benefits

### 1. **Consistency**
- Follows the same pattern as other AI tasks
- Model selection via task content (not hardcoded)
- Service abstraction for business logic

### 2. **Flexibility**
- Easy to change AI model per task
- No hardcoded weights to maintain
- AI adapts reasoning to context

### 3. **Maintainability**
- Clear separation of concerns
- Easier to test and debug
- Less code to maintain (removed ~150 lines)

### 4. **Scalability**
- Rich context enables better decisions
- Can easily add new Wikidata signals
- AI learns from patterns vs fixed rules

---

## API Integration (NestJS)

**Required Changes:**
1. Add `model` field to severity task creation
2. Default to `gpt-4o-mini` if not specified
3. Keep everything else the same

**Example Task Creation:**
```typescript
await this.aiTaskService.create({
  type: 'defining_severity',
  content: {
    verificationId: vr._id,
    impactAreaWikidataId: vr.impactArea.wikidataId,
    topicsWikidataIds: vr.topics.map(t => t.wikidataId),
    personalityWikidataId: vr.identifyingData?.personalityWikidataId,
    contentSummary: vr.content,
    model: 'gpt-4o-mini'  // ← Add this
  },
  callbackRoute: 'verification_update_defining_severity',
  callbackParams: { targetId: vr._id, field: 'severity' }
});
```

---

## Testing

**Run tests:**
```bash
# Copy test file to container
docker cp test_severity_processor.py ai-task-processor:/app/

# Run tests
docker-compose exec ai-task-processor python test_severity_processor.py
```

**Or locally:**
```bash
python test_severity_processor.py
```

---

## Performance Considerations

### Wikidata API Calls
- **Parallel execution:** `asyncio.gather()` for inbound links + pageviews
- **Timeouts:** 10s for SPARQL, 10s for Wikipedia API
- **Fallbacks:** Returns 0 on API failures (doesn't block task)

### OpenAI API
- **Model:** `gpt-4o-mini` (fast + cost-effective)
- **Retry logic:** Built into `openai_client`
- **Fallback:** Returns `medium_2` if response unclear

---

## Migration Path

1. ✅ **Phase 1 (Done):** Refactor Python processor
2. **Phase 2:** Update NestJS to send `model` field
3. **Phase 3:** Test with real data
4. **Phase 4:** Monitor AI classification quality
5. **Phase 5:** Fine-tune prompts based on results

---

## Questions?

**Q: What if Wikidata is slow?**
A: Uses 10s timeouts + fallback to 0 values. Task continues.

**Q: What if OpenAI returns unclear response?**
A: Falls back to `medium_2` severity.

**Q: Can we adjust the AI prompt?**
A: Yes! Edit `_build_severity_prompt()` in `defining_severity.py`.

**Q: Can we use different AI models?**
A: Yes! Pass any OpenAI model via `task.content.model`.

**Q: What about costs?**
A: `gpt-4o-mini` is ~60x cheaper than GPT-4, optimized for reasoning.
