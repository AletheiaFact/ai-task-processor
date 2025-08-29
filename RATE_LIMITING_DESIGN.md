# Multi-Tier Rate Limiting System Design

## Overview
Implementation of hierarchical rate limiting for AI task processing with support for multiple time periods: minute, hour, day, week, and month quotas. This system provides both burst protection and long-term budget control.

## Current System Analysis
### Existing Limits
- **Concurrency Only**: Current system has `CONCURRENCY_LIMIT=5` (simultaneous processing)
- **No Time-Based Limits**: Missing rate limiting over time windows
- **No Persistent Tracking**: Counters reset on service restart
- **No Long-term Budgets**: Cannot control weekly/monthly usage

### Gap Analysis
- ❌ No burst protection (tasks/minute)
- ❌ No hourly rate control
- ❌ No daily quotas
- ❌ No weekly budget limits
- ❌ No monthly budget limits
- ❌ No persistent storage for long-term tracking

## Design Requirements

### Functional Requirements
1. **Multi-Period Support**: minute, hour, day, week, month limits
2. **Hierarchical Checking**: All limits must pass before processing
3. **Persistent Storage**: Survive service restarts for long-term limits
4. **Performance**: Minimal impact on task processing speed
5. **Monitoring**: Prometheus metrics for each time period
6. **Configuration**: Environment variable based configuration

### Non-Functional Requirements
1. **Accuracy**: ±1 task accuracy for all periods
2. **Performance**: <10ms overhead per batch check
3. **Reliability**: ACID compliance for counter updates
4. **Scalability**: Support up to 100K tasks/month tracking

## Architecture Design

### 1. Configuration Structure
```bash
# Short-term limits (in-memory, fast checks)
RATE_LIMIT_PER_MINUTE=20        # Burst protection
RATE_LIMIT_PER_HOUR=100         # Hourly rate control

# Long-term limits (persistent storage)
RATE_LIMIT_PER_DAY=500          # Daily quotas
RATE_LIMIT_PER_WEEK=2000        # Weekly budget
RATE_LIMIT_PER_MONTH=7500       # Monthly budget

# Storage configuration
RATE_LIMIT_STORAGE_PATH=/app/data/rate_limits.db
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STRATEGY=rolling     # 'rolling' or 'fixed'
```

### 2. Data Storage Schema

#### SQLite Database Structure
```sql
-- Primary rate limit counters
CREATE TABLE rate_limits (
    time_period TEXT PRIMARY KEY,  -- 'day', 'week', 'month'
    current_count INTEGER DEFAULT 0,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Task completion log for rolling windows
CREATE TABLE task_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    task_type TEXT,
    task_id TEXT
);

-- Indices for performance
CREATE INDEX idx_task_completions_timestamp ON task_completions(completed_at);
CREATE INDEX idx_rate_limits_period ON rate_limits(time_period);
```

### 3. Component Architecture

#### RateLimiter Class
```python
class RateLimiter:
    def __init__(self, db_path: str)
    async def check_all_limits(self, task_count: int = 1) -> RateLimitResult
    async def record_completed_tasks(self, task_count: int)
    async def get_current_usage(self) -> Dict[str, Usage]
    async def reset_expired_windows(self)
```

#### Integration Points
- **TaskScheduler**: Check limits before processing batch
- **Settings**: New configuration parameters
- **Metrics**: New Prometheus counters for each period
- **Database**: SQLite initialization and migration

### 4. Processing Flow

#### Rate Limit Check Flow
```
1. TaskScheduler.poll_and_process_tasks()
2. rate_limiter.check_all_limits(batch_size)
3. For each period (minute/hour/day/week/month):
   - Get current window boundaries
   - Count tasks in current window
   - Compare against configured limit
4. If ANY limit exceeded → skip processing, log reason
5. If all limits OK → proceed with task processing
6. After successful processing → record_completed_tasks()
```

#### Window Management
```
Rolling Windows (default):
- Minute: Last 60 seconds
- Hour: Last 3600 seconds  
- Day: Last 24 hours
- Week: Last 7 days
- Month: Last 30 days

Fixed Windows (optional):
- Day: 00:00-23:59 UTC
- Week: Monday 00:00 - Sunday 23:59
- Month: 1st 00:00 - Last day 23:59
```

### 5. Storage Strategy

#### Hybrid Approach (Performance Optimized)
- **In-Memory**: minute, hour counters (fast access)
- **Database**: day, week, month counters (persistence required)
- **Sync Strategy**: Write to DB every 10 completed tasks
- **Recovery**: Load from DB on service startup

#### Data Retention
- **task_completions**: Keep last 35 days (covers monthly rolling window)
- **rate_limits**: Keep all periods indefinitely
- **Cleanup**: Daily job to remove old task_completions records

## Implementation Plan

### Phase 1: Core Infrastructure
1. **Database Setup**
   - Create SQLite schema
   - Add migration system
   - Database initialization in startup

2. **Configuration**
   - Add rate limiting settings to `settings.py`
   - Environment variable validation
   - Default values and documentation

3. **RateLimiter Class**
   - Core rate limiting logic
   - Database operations
   - Window calculations

### Phase 2: Integration
1. **TaskScheduler Integration**
   - Pre-processing rate limit checks
   - Post-processing task recording
   - Error handling for limit exceeded

2. **Metrics Enhancement**
   - Prometheus counters for each period
   - Current usage gauges
   - Limit exceeded events counter

### Phase 3: Monitoring & Operations
1. **Health Checks**
   - Rate limit status in health endpoint
   - Database connectivity checks

2. **Logging**
   - Rate limit exceeded warnings
   - Usage milestone logging
   - Performance metrics

## Error Handling

### Rate Limit Exceeded Scenarios
1. **Graceful Degradation**: Skip processing, continue service
2. **Informative Logging**: Log which limit was exceeded
3. **Metrics Recording**: Track limit exceeded events
4. **Client Notification**: Consider webhook for limit warnings

### Database Failure Scenarios
1. **Fallback Mode**: Disable long-term limits, keep short-term
2. **Recovery**: Auto-retry database operations
3. **Monitoring**: Alert on database connection failures

## Testing Strategy

### Unit Tests
- Rate limiting logic for each time period
- Window boundary calculations
- Database operations (CRUD)
- Configuration validation

### Integration Tests
- End-to-end task processing with limits
- Service restart persistence
- Multiple period limit interactions

### Performance Tests
- Rate limit check overhead measurement
- Database operation benchmarks
- Memory usage under high task loads

## Monitoring & Observability

### New Prometheus Metrics
```python
rate_limit_current_usage = Gauge('rate_limit_current_usage', 'Current usage for time period', ['period'])
rate_limit_max_allowed = Gauge('rate_limit_max_allowed', 'Maximum allowed for time period', ['period'])  
rate_limit_exceeded_total = Counter('rate_limit_exceeded_total', 'Rate limit exceeded events', ['period'])
rate_limit_check_duration = Histogram('rate_limit_check_duration_seconds', 'Time to check rate limits')
```

### Dashboard Queries
```promql
# Usage percentage by period
(rate_limit_current_usage / rate_limit_max_allowed) * 100

# Time until limit reset
rate_limit_window_reset_seconds

# Rate of limit exceeded events
rate(rate_limit_exceeded_total[5m])
```

## Migration Strategy

### Rollout Plan
1. **Feature Flag**: `RATE_LIMIT_ENABLED=false` by default
2. **Gradual Activation**: Enable in test environments first
3. **Monitoring**: Watch performance impact
4. **Production**: Enable with conservative limits initially

### Backwards Compatibility
- All new features are additive
- Existing concurrency limiting unchanged
- No breaking changes to existing APIs

## Future Enhancements

### Potential Extensions
1. **Per-Task-Type Limits**: Different limits for embeddings vs completions
2. **Dynamic Limits**: Adjust based on time of day/load
3. **Distributed Limits**: Share limits across multiple instances
4. **Cost-Based Limits**: Track API costs instead of task counts
5. **Priority Queues**: High-priority tasks can exceed certain limits

---

**Implementation Status**: Ready for development
**Estimated Effort**: 2-3 days development + testing
**Dependencies**: SQLite (already available), asyncio, aiosqlite