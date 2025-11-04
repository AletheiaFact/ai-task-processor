# Field Changes Summary - Severity Task

## Changes Made

### 1. Removed `verificationId` from content
**Reason:** Redundant - already present in `callbackParams.targetId`

**Before:**
```json
{
  "content": {
    "verificationId": "vr_123",
    ...
  },
  "callbackParams": {
    "targetId": "vr_123"
  }
}
```

**After:**
```json
{
  "content": {
    // verificationId removed
    ...
  },
  "callbackParams": {
    "targetId": "vr_123"  // Use this instead
  }
}
```

---

### 2. Renamed `contentSummary` to `text`
**Reason:** Consistency with other AI tasks (identifying_data, defining_topics, etc.)

**Before:**
```json
{
  "content": {
    "contentSummary": "Statement about climate action"
  }
}
```

**After:**
```json
{
  "content": {
    "text": "Statement about climate action"
  }
}
```

---

## Updated Task Format

```json
{
  "type": "defining_severity",
  "content": {
    "impactAreaWikidataId": "Q8068",
    "topicsWikidataIds": ["Q7942", "Q12739"],
    "personalityWikidataId": "Q22571744",
    "text": "Text content being fact-checked",
    "model": "gpt-4o-mini"
  },
  "callbackRoute": "verification_update_defining_severity",
  "callbackParams": {
    "targetId": "vr_123",  // Verification Request ID goes here
    "field": "severity"
  }
}
```

---

## Files Updated

- ✅ `ai_task_processor/models/task.py` - Updated `DefiningSeverityInput` model
- ✅ `ai_task_processor/services/defining_severity.py` - Updated service to use `text`
- ✅ `ai_task_processor/processors/defining_severity.py` - Updated processor
- ✅ `test_severity_processor.py` - Updated all test cases
- ✅ `docs/NESTJS_SEVERITY_TASK_FORMAT.md` - Updated documentation

---

## Migration Guide for NestJS

**Old code:**
```typescript
const task = await this.aiTaskService.create({
  type: 'defining_severity',
  content: {
    verificationId: vr._id.toString(),        // ❌ Remove
    contentSummary: vr.content,               // ❌ Rename
    impactAreaWikidataId: vr.impactArea.wikidataId,
    topicsWikidataIds: vr.topics.map(t => t.wikidataId),
    personalityWikidataId: vr.identifyingData?.personalityWikidataId,
    model: 'gpt-4o-mini'
  },
  callbackRoute: 'verification_update_defining_severity',
  callbackParams: {
    targetId: vr._id.toString(),
    field: 'severity'
  }
});
```

**New code:**
```typescript
const task = await this.aiTaskService.create({
  type: 'defining_severity',
  content: {
    // verificationId removed - already in targetId
    text: vr.content,                         // ✅ Renamed from contentSummary
    impactAreaWikidataId: vr.impactArea.wikidataId,
    topicsWikidataIds: vr.topics.map(t => t.wikidataId),
    personalityWikidataId: vr.identifyingData?.personalityWikidataId,
    model: 'gpt-4o-mini'
  },
  callbackRoute: 'verification_update_defining_severity',
  callbackParams: {
    targetId: vr._id.toString(),              // ✅ Verification ID here
    field: 'severity'
  }
});
```

---

## Summary

**Two simple changes:**
1. ❌ Remove `verificationId` from content (use `targetId` instead)
2. ✅ Rename `contentSummary` → `text`

That's it! 🎉
