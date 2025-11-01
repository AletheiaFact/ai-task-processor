# NestJS AI Task Format for Severity Definition

## Quick Reference

### Task Creation Payload

```typescript
// POST /api/ai-tasks
{
  "type": "defining_severity",
  "content": {
    "impactAreaWikidataId": string,
    "topicsWikidataIds": string[],
    "personalityWikidataId": string | null,
    "text": string,
    "model": string  // Default: "gpt-4o-mini"
  },
  "callbackRoute": "verification_update_defining_severity",
  "callbackParams": {
    "targetId": string,  // Verification Request ID
    "field": "severity"
  }
}
```

---

## Complete Example

```typescript
// In your NestJS service
async createSeverityTask(verificationRequest: VerificationRequest) {
  const task = await this.aiTaskService.create({
    type: 'defining_severity',
    content: {
      // Required: Impact area Wikidata ID (from defining_impact_area task result)
      impactAreaWikidataId: verificationRequest.impactArea.wikidataId,

      // Required: Topics Wikidata IDs (from defining_topics task result)
      topicsWikidataIds: verificationRequest.topics.map(t => t.wikidataId),

      // Optional: Personality Wikidata ID (from identifying_data task result)
      personalityWikidataId: verificationRequest.identifyingData?.personalityWikidataId || null,

      // Required: Text content being fact-checked
      text: verificationRequest.content,

      // Optional: AI model to use (defaults to "gpt-4o-mini" if not provided)
      model: "gpt-4o-mini"  // or "gpt-4o", "gpt-4-turbo", etc.
    },
    callbackRoute: 'verification_update_defining_severity',
    callbackParams: {
      targetId: verificationRequest._id.toString(),  // Verification Request ID in targetId
      field: 'severity'
    }
  });

  return task;
}
```

---

## Field Descriptions

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `impactAreaWikidataId` | string | ✅ | Wikidata ID from defining_impact_area task | `"Q8068"` (Environment) |
| `topicsWikidataIds` | string[] | ✅ | Wikidata IDs from defining_topics task | `["Q7942", "Q12739"]` |
| `personalityWikidataId` | string \| null | ❌ | Wikidata ID from identifying_data task | `"Q22571744"` (Greta Thunberg) |
| `text` | string | ✅ | Text content being fact-checked | `"Statement about climate action"` |
| `model` | string | ❌ | OpenAI model for reasoning | `"gpt-4o-mini"` (default) |

**Note:** The `targetId` in `callbackParams` contains the Verification Request ID, so no need to duplicate it in `content`.

---

## Expected Response Format

Python processor will return via callback:

```typescript
// PATCH /api/verification-requests/:id/severity
{
  "state": "succeeded",
  "result": {
    "severity": "high_3"  // SeverityEnum value
  }
}
```

### Severity Enum Values

```typescript
enum SeverityEnum {
  CRITICAL = "critical",      // Extremely urgent, widespread impact
  HIGH_3 = "high_3",          // Very high severity
  HIGH_2 = "high_2",          // High severity
  HIGH_1 = "high_1",          // High severity
  MEDIUM_3 = "medium_3",      // Moderate-high severity
  MEDIUM_2 = "medium_2",      // Moderate severity
  MEDIUM_1 = "medium_1",      // Moderate-low severity
  LOW_3 = "low_3",            // Low-moderate severity
  LOW_2 = "low_2",            // Low severity
  LOW_1 = "low_1"             // Very low severity
}
```

---

## Prerequisites

⚠️ **This task requires other AI tasks to be completed first:**

1. ✅ `defining_impact_area` → Provides `impactAreaWikidataId`
2. ✅ `defining_topics` → Provides `topicsWikidataIds[]`
3. ✅ `identifying_data` → Provides `personalityWikidataId` (optional)

**Workflow:**
```
Verification Request Created
  ↓
Run: identifying_data (parallel)
Run: defining_topics (parallel)
Run: defining_impact_area (parallel)
  ↓
Wait for all to complete
  ↓
Extract Wikidata IDs from results
  ↓
Create defining_severity task ← YOU ARE HERE
```

---

## Implementation Example (NestJS)

```typescript
// ai-task.service.ts
async createSeverityTask(
  verificationId: string,
  impactAreaWikidataId: string,
  topicsWikidataIds: string[],
  personalityWikidataId: string | null,
  text: string,
  model: string = 'gpt-4o-mini'
): Promise<AITask> {

  // Validate required fields
  if (!impactAreaWikidataId) {
    throw new BadRequestException('impactAreaWikidataId is required');
  }

  if (!topicsWikidataIds || topicsWikidataIds.length === 0) {
    throw new BadRequestException('topicsWikidataIds is required and must not be empty');
  }

  if (!text) {
    throw new BadRequestException('text is required');
  }

  // Create AI task
  const task = await this.aiTaskModel.create({
    type: 'defining_severity',
    state: 'pending',
    content: {
      impactAreaWikidataId,
      topicsWikidataIds,
      personalityWikidataId,
      text,
      model
    },
    callbackRoute: 'verification_update_defining_severity',
    callbackParams: {
      targetId: verificationId,  // Verification Request ID goes in targetId
      field: 'severity'
    },
    createdAt: new Date()
  });

  this.logger.log(
    `Created defining_severity task for verification ${verificationId}`,
    {
      taskId: task._id,
      impactAreaWikidataId,
      topicsCount: topicsWikidataIds.length,
      hasPersonality: !!personalityWikidataId,
      textLength: text.length,
      model
    }
  );

  return task;
}
```

---

## Callback Handler Example

```typescript
// verification-request.controller.ts
@Patch(':id/severity')
async updateSeverity(
  @Param('id') id: string,
  @Body() body: { state: string; result: { severity: string } }
) {
  this.logger.log(`Updating severity for verification ${id}`, body);

  if (body.state === 'succeeded') {
    const severity = body.result.severity;

    // Validate severity enum
    const validSeverities = [
      'critical', 'high_3', 'high_2', 'high_1',
      'medium_3', 'medium_2', 'medium_1',
      'low_3', 'low_2', 'low_1'
    ];

    if (!validSeverities.includes(severity)) {
      throw new BadRequestException(`Invalid severity value: ${severity}`);
    }

    // Update verification request
    await this.verificationRequestModel.findByIdAndUpdate(id, {
      severity: severity,
      severityUpdatedAt: new Date()
    });

    this.logger.log(`Severity updated successfully: ${severity}`);
    return { success: true, severity };
  } else {
    this.logger.error(`Severity task failed for verification ${id}`);
    throw new InternalServerErrorException('Severity calculation failed');
  }
}
```

---

## Testing Examples

### Example 1: Climate Change with Personality
```json
{
  "type": "defining_severity",
  "content": {
    "impactAreaWikidataId": "Q8068",
    "topicsWikidataIds": ["Q7942", "Q12739"],
    "personalityWikidataId": "Q22571744",
    "text": "Greta Thunberg claims urgent climate action needed",
    "model": "gpt-4o-mini"
  },
  "callbackRoute": "verification_update_defining_severity",
  "callbackParams": {
    "targetId": "vr_climate_001",
    "field": "severity"
  }
}
```
**Expected Result:** `high_2` or `high_3` (climate + influential personality)

---

### Example 2: Health without Personality
```json
{
  "type": "defining_severity",
  "content": {
    "impactAreaWikidataId": "Q12195",
    "topicsWikidataIds": ["Q134768", "Q189603"],
    "personalityWikidataId": null,
    "text": "Report about new vaccination policy",
    "model": "gpt-4o-mini"
  },
  "callbackRoute": "verification_update_defining_severity",
  "callbackParams": {
    "targetId": "vr_health_002",
    "field": "severity"
  }
}
```
**Expected Result:** `high_1` or `medium_3` (health is important)

---

### Example 3: Entertainment
```json
{
  "type": "defining_severity",
  "content": {
    "impactAreaWikidataId": "Q173799",
    "topicsWikidataIds": ["Q638", "Q182832"],
    "personalityWikidataId": null,
    "text": "News about upcoming concert event",
    "model": "gpt-4o-mini"
  },
  "callbackRoute": "verification_update_defining_severity",
  "callbackParams": {
    "targetId": "vr_entertainment_003",
    "field": "severity"
  }
}
```
**Expected Result:** `low_1` or `low_2` (entertainment is low priority)

## Error Handling

```typescript
// Common errors and how to handle them

// 1. Missing required fields
{
  "error": "Model is required in task content"
}
// Fix: Add model parameter to content

// 2. Invalid Wikidata IDs
{
  "state": "succeeded",
  "result": {
    "severity": "medium_2"  // Fallback when data is missing
  }
}
// Python processor handles gracefully with defaults

// 3. OpenAI API failure
{
  "state": "failed",
  "error": "Retryable error: Rate limit exceeded"
}
// Task will be retried automatically

// 4. Invalid model
{
  "error": "Requested model 'invalid-model' is not supported"
}
// Fix: Use valid OpenAI model name
```

---

## Quick Checklist

Before creating severity task:
- [ ] ✅ `identifying_data` task completed
- [ ] ✅ `defining_topics` task completed
- [ ] ✅ `defining_impact_area` task completed
- [ ] ✅ Extract Wikidata IDs from task results
- [ ] ✅ Prepare content summary
- [ ] ✅ Choose AI model (or use default)
- [ ] ✅ Create task with proper callback route

---
