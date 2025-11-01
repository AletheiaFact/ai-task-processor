# Severity Task Architecture Summary

## Overview
The severity definition system uses a **split architecture** where NestJS sends minimal data and the Python AI processor handles all Wikidata enrichment and scoring.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  NestJS Application                                              │
│                                                                  │
│  1. Verification Request completed (all AI tasks done)          │
│  2. Extract Wikidata IDs from completed tasks:                  │
│     - impactAreaWikidataId (from defining_impact_area task)    │
│     - topicsWikidataIds (from defining_topics task)            │
│     - personalityWikidataId (from identifying_data task)       │
│  3. Create AI task with Wikidata IDs:                          │
│     - verificationId                                            │
│     - impactAreaWikidataId (string: "Q8068")                   │
│     - topicsWikidataIds (array: ["Q7942", "Q12739"])          │
│     - personalityWikidataId (string: "Q456789" or null)        │
│     - contentSummary (string)                                   │
│  4. POST task to AI processor                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Python AI Processor (SIMPLIFIED!)                              │
│                                                                  │
│  1. Receive task from polling                                   │
│  2. Fetch Wikidata data BY ID (no search needed!):             │
│     - get_personality_data(wikidataId) if provided             │
│     - get_topic_data_by_id(wikidataId) for each topic         │
│     - get_impact_area_data_by_id(wikidataId) for impact       │
│                                                                  │
│  3. Calculate component scores:                                 │
│     - Personality score (0-10) if exists                        │
│     - Impact area score (0-10)                                  │
│     - Topics score (0-10)                                       │
│                                                                  │
│  4. Apply hardcoded weights:                                    │
│     IF personality exists:                                      │
│       severity = personality×0.30 + impact×0.40 + topics×0.30   │
│     ELSE:                                                       │
│       severity = impact×0.57 + topics×0.43                      │
│                                                                  │
│  5. Generate detailed reasoning (logged, not returned)         │
│  6. Map numeric score to SeverityEnum                           │
│  7. Send result back to NestJS                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  NestJS Callback Handler                                         │
│                                                                  │
│  1. Receive severity result via PATCH callback                  │
│  2. Update Verification Request:                                │
│     - severity: "high_3" (SeverityEnum only - MVP simplified)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## NestJS Responsibilities (Even Simpler!)

### ✅ What NestJS Does:
1. **Validate prerequisites** - Ensure impact area, topics, and identifying data exist
2. **Extract Wikidata IDs** - Get IDs from completed AI task results:
   - `verificationRequest.impactArea` (has `wikidataId` field)
   - `verificationRequest.topics[]` (each has `wikidataId` field)
   - `verificationRequest.identifyingData.personalityWikidataId` (nullable)
3. **Create task with IDs** - Build task with Wikidata IDs (no text labels)
4. **Handle callback** - Receive and store severity results
5. **Trigger workflow** - Create severity task after all other AI tasks complete

### ❌ What NestJS Does NOT Do:
- ❌ Search for Wikidata IDs (already has them!)
- ❌ Query Wikidata API
- ❌ Calculate scores
- ❌ Apply weights
- ❌ Generate reasoning

**Code needed in NestJS (MVP Simplified)**: ~60 lines total
- `AITaskService.createSeverityTask()` - ~35 lines (+ ID extraction)
- `VerificationRequestController.updateSeverity()` - ~20 lines
- Schema updates - ~5 lines (just severity enum field)

---

## Python Processor Responsibilities (Lighter Now!)

### ✅ What Python Does:
1. **Wikidata data fetching** - Fetch entity data by ID (no search!)
2. **Scoring algorithms** - Calculate all component scores
3. **Weight application** - Apply hardcoded weights (30/40/30 vs 0/57/43)
4. **Reasoning generation** - Create human-readable explanations (logged)
5. **Error handling** - Fallback to defaults when Wikidata fails

### ❌ What Python Does NOT Do Anymore:
- ❌ Search for Wikidata IDs (receives them directly!)
- ❌ Return detailed score breakdown (MVP: only severity enum)

**Code needed in Python**: ~500 lines total (reduced!)
- `wikidata_enrichment.py` - ~200 lines (simpler, no search)
- `DefiningSeverityProcessor` - ~250 lines
- Removed ~100 lines of search logic!

---

## Configuration

### Hardcoded Weights (in Python)
```python
# When personality exists:
WEIGHTS_WITH_PERSONALITY = {
    "personality": 0.30,  # 30%
    "impact_area": 0.40,  # 40%
    "topics": 0.30        # 30%
}

# When no personality:
WEIGHTS_WITHOUT_PERSONALITY = {
    "impact_area": 0.57,  # 57% (0.40 + 0.30×0.57)
    "topics": 0.43        # 43% (0.30 + 0.30×0.43)
}
```

### Impact Area Priorities (in Python)
```python
IMPACT_AREA_PRIORITIES = {
    "security": {"priority": 10, "urgency": 10, "impact": 10},
    "health": {"priority": 10, "urgency": 9, "impact": 10},
    "environment": {"priority": 9, "urgency": 10, "impact": 10},
    "education": {"priority": 8, "urgency": 7, "impact": 9},
    # ... more areas
}
```

---

## Task Schema

### NestJS Creates This Task:
```json
{
  "type": "defining_severity",
  "content": {
    "verificationId": "vr_123456789",
    "impactAreaWikidataId": "Q8068",
    "topicsWikidataIds": ["Q7942", "Q12739"],
    "personalityWikidataId": "Q456789",
    "contentSummary": "Statement about climate action..."
  },
  "callbackRoute": "verification_update_defining_severity",
  "callbackParams": {
    "targetId": "vr_123456789",
    "field": "severity"
  }
}
```

**Key Change**: NestJS now sends **Wikidata IDs directly** instead of text labels. This eliminates the search step in Python.

### Python Returns This Result (MVP - Simplified):
```json
{
  "state": "succeeded",
  "result": {
    "severity": "high_3"
  }
}
```

**Internal Processing (Logged but not returned)**:
- Numeric score: 8.7
- Component scores: personality=9.2, impactArea=9.5, topics=7.8
- Reasoning: Generated but only logged
- All details available in Python logs for debugging

### Severity Enum Mapping
```python
# Python processor maps numeric score to NestJS SeverityEnum:
9.1-10.0 → "critical"
8.1-9.0  → "high_3"
7.1-8.0  → "high_2"
6.1-7.0  → "high_1"
5.1-6.0  → "medium_3"
4.1-5.0  → "medium_2"
3.1-4.0  → "medium_1"
2.1-3.0  → "low_3"
1.1-2.0  → "low_2"
1.0-1.0  → "low_1"
```

---

## Implementation Priority

### Phase 1: NestJS (Simple - Start Here!)
1. Add `createSeverityTask()` to `AITaskService`
2. Add `verification_update_defining_severity` endpoint
3. Update `VerificationRequest` schema
4. Test task creation

**Estimated time**: 2-3 hours

### Phase 2: Python Wikidata Client
1. Create `WikidataClient` class
2. Implement API methods
3. Add scoring algorithms
4. Test with real Wikidata IDs

**Estimated time**: 4-6 hours

### Phase 3: Python Severity Processor
1. Create `DefiningSeverityProcessor`
2. Integrate WikidataClient
3. Implement severity calculation
4. Generate reasoning
5. Register in ProcessorFactory

**Estimated time**: 3-4 hours

### Phase 4: Integration Testing
1. End-to-end flow test
2. Test with/without personality
3. Test Wikidata failures
4. Performance testing

**Estimated time**: 2-3 hours

---

## Key Benefits of This Architecture

✅ **Separation of Concerns**: NestJS handles workflow, Python handles AI logic
✅ **Simplicity**: NestJS code is minimal (~55 lines for MVP)
✅ **Flexibility**: Easy to adjust weights and scoring in Python
✅ **Reusability**: WikidataClient can be used for other features
✅ **Testability**: Each component can be tested independently
✅ **Error Handling**: Python gracefully handles Wikidata failures
✅ **Type Safety**: Uses your existing SeverityEnum for consistency
✅ **MVP-Ready**: Simple response, full details logged for debugging
✅ **Extensible**: Can easily add score/details fields in future versions

---

## Questions?

- **Q**: What if Wikidata is slow?
  **A**: WikidataClient includes timeouts and fallback defaults

- **Q**: Can we adjust weights later?
  **A**: Yes! Just modify the hardcoded weights in Python processor

- **Q**: What if personality has no followers data?
  **A**: WikidataClient uses defaults (0 followers, moderate scores)

- **Q**: How do we test without real Wikidata IDs?
  **A**: Use mock data or test with known IDs (Q456789 = Greta Thunberg)
