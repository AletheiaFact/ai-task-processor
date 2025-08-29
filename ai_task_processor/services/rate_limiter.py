import asyncio
import aiosqlite
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass
from enum import Enum

from ..config import settings, RateLimitStrategy
from ..utils import get_logger

logger = get_logger(__name__)


class RateLimitPeriod(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class RateLimitResult:
    allowed: bool
    period_exceeded: Optional[str] = None
    current_usage: Dict[str, int] = None
    limits: Dict[str, int] = None
    reset_times: Dict[str, datetime] = None


@dataclass
class Usage:
    current: int
    limit: int
    remaining: int
    reset_at: datetime
    window_start: datetime


class RateLimiter:
    """
    Multi-tier rate limiter supporting minute, hour, day, week, and month limits.
    Uses SQLite for persistent storage of long-term counters.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.rate_limit_storage_path
        self.strategy = settings.rate_limit_strategy
        
        # In-memory counters for short-term limits (performance)
        self._minute_counter = 0
        self._hour_counter = 0
        self._minute_window_start = datetime.now(timezone.utc)
        self._hour_window_start = datetime.now(timezone.utc)
        
        # Period configurations
        self.limits = {
            RateLimitPeriod.MINUTE: settings.rate_limit_per_minute,
            RateLimitPeriod.HOUR: settings.rate_limit_per_hour,
            RateLimitPeriod.DAY: settings.rate_limit_per_day,
            RateLimitPeriod.WEEK: settings.rate_limit_per_week,
            RateLimitPeriod.MONTH: settings.rate_limit_per_month,
        }
        
        # Period durations in seconds
        self.period_seconds = {
            RateLimitPeriod.MINUTE: 60,
            RateLimitPeriod.HOUR: 3600,
            RateLimitPeriod.DAY: 86400,
            RateLimitPeriod.WEEK: 604800,
            RateLimitPeriod.MONTH: 2592000,  # 30 days
        }
        
        self._initialized = False
        logger.info("Rate limiter initialized", 
                   strategy=self.strategy.value,
                   db_path=self.db_path,
                   limits={k.value: v for k, v in self.limits.items() if v > 0})
    
    async def initialize(self):
        """Initialize database schema and load existing counters"""
        if self._initialized:
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables_with_connection(db)
            await self._load_existing_counters_with_connection(db)
            
        self._initialized = True
        logger.info("Rate limiter database initialized")
    
    async def _create_tables_with_connection(self, db):
        """Create SQLite tables for rate limiting using provided connection"""
        # Rate limits table for persistent counters
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                time_period TEXT PRIMARY KEY,
                current_count INTEGER DEFAULT 0,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Task completions log for rolling windows
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                task_type TEXT,
                task_id TEXT
            )
        """)
        
        # Indices for performance
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_completions_timestamp 
            ON task_completions(completed_at)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_rate_limits_period 
            ON rate_limits(time_period)
        """)
        
        await db.commit()
    
    async def _create_tables(self):
        """Create SQLite tables for rate limiting"""
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables_with_connection(db)
    
    async def _load_existing_counters_with_connection(self, db):
        """Load existing counters from database using provided connection"""
        cursor = await db.execute("""
            SELECT time_period, current_count, window_start, window_end
            FROM rate_limits
            WHERE time_period IN ('day', 'week', 'month')
        """)
        
        rows = await cursor.fetchall()
        for row in rows:
            period, count, window_start, window_end = row
            window_start_dt = datetime.fromisoformat(window_start.replace('Z', '+00:00'))
            window_end_dt = datetime.fromisoformat(window_end.replace('Z', '+00:00'))
            
            # Check if window is still valid
            now = datetime.now(timezone.utc)
            if now < window_end_dt:
                logger.info(f"Loaded existing {period} counter", 
                          count=count, 
                          window_start=window_start_dt,
                          window_end=window_end_dt)

    async def _load_existing_counters(self):
        """Load existing counters from database on startup"""
        async with aiosqlite.connect(self.db_path) as db:
            await self._load_existing_counters_with_connection(db)
    
    def _get_window_boundaries(self, period: RateLimitPeriod, now: datetime) -> tuple[datetime, datetime]:
        """Get window start and end times for a given period"""
        if self.strategy == RateLimitStrategy.ROLLING:
            return self._get_rolling_window(period, now)
        else:
            return self._get_fixed_window(period, now)
    
    def _get_rolling_window(self, period: RateLimitPeriod, now: datetime) -> tuple[datetime, datetime]:
        """Get rolling window boundaries (last N seconds)"""
        duration = timedelta(seconds=self.period_seconds[period])
        window_start = now - duration
        window_end = now
        return window_start, window_end
    
    def _get_fixed_window(self, period: RateLimitPeriod, now: datetime) -> tuple[datetime, datetime]:
        """Get fixed window boundaries (calendar-based)"""
        if period == RateLimitPeriod.MINUTE:
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + timedelta(minutes=1)
        elif period == RateLimitPeriod.HOUR:
            window_start = now.replace(minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(hours=1)
        elif period == RateLimitPeriod.DAY:
            window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(days=1)
        elif period == RateLimitPeriod.WEEK:
            # Monday = 0, Sunday = 6
            days_since_monday = now.weekday()
            window_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(weeks=1)
        elif period == RateLimitPeriod.MONTH:
            window_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Next month
            if now.month == 12:
                window_end = window_start.replace(year=now.year + 1, month=1)
            else:
                window_end = window_start.replace(month=now.month + 1)
        
        return window_start, window_end
    
    async def _get_current_usage_in_memory(self, period: RateLimitPeriod, now: datetime) -> int:
        """Get current usage for in-memory counters (minute/hour)"""
        if period == RateLimitPeriod.MINUTE:
            window_start, _ = self._get_window_boundaries(period, now)
            if window_start > self._minute_window_start:
                # Window expired, reset counter
                self._minute_counter = 0
                self._minute_window_start = window_start
            return self._minute_counter
            
        elif period == RateLimitPeriod.HOUR:
            window_start, _ = self._get_window_boundaries(period, now)
            if window_start > self._hour_window_start:
                # Window expired, reset counter
                self._hour_counter = 0
                self._hour_window_start = window_start
            return self._hour_counter
            
        return 0
    
    async def _get_current_usage_database(self, period: RateLimitPeriod, now: datetime) -> int:
        """Get current usage for database-stored counters (day/week/month)"""
        window_start, window_end = self._get_window_boundaries(period, now)
        
        if self.strategy == RateLimitStrategy.ROLLING:
            # For rolling windows, count tasks in the time range
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM task_completions 
                    WHERE completed_at >= ? AND completed_at <= ?
                """, (window_start.isoformat(), now.isoformat()))
                
                row = await cursor.fetchone()
                return row[0] if row else 0
        else:
            # For fixed windows, use stored counter
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT current_count FROM rate_limits 
                    WHERE time_period = ? AND window_start <= ? AND window_end > ?
                """, (period.value, now.isoformat(), now.isoformat()))
                
                row = await cursor.fetchone()
                if row:
                    return row[0]
                else:
                    # Initialize new window
                    await db.execute("""
                        INSERT OR REPLACE INTO rate_limits 
                        (time_period, current_count, window_start, window_end)
                        VALUES (?, 0, ?, ?)
                    """, (period.value, window_start.isoformat(), window_end.isoformat()))
                    await db.commit()
                    return 0
    
    async def check_all_limits(self, task_count: int = 1) -> RateLimitResult:
        """
        Check all configured rate limits before allowing task processing.
        Returns RateLimitResult with allowed status and usage details.
        """
        if not settings.rate_limit_enabled:
            return RateLimitResult(allowed=True)
        
        await self.initialize()
        
        now = datetime.now(timezone.utc)
        current_usage = {}
        reset_times = {}
        
        # Check each configured limit
        for period, limit in self.limits.items():
            if limit <= 0:  # Disabled
                continue
                
            # Get current usage
            if period in [RateLimitPeriod.MINUTE, RateLimitPeriod.HOUR]:
                usage = await self._get_current_usage_in_memory(period, now)
            else:
                usage = await self._get_current_usage_database(period, now)
            
            current_usage[period.value] = usage
            
            # Get reset time
            _, window_end = self._get_window_boundaries(period, now)
            reset_times[period.value] = window_end
            
            # Check if adding task_count would exceed limit
            if usage + task_count > limit:
                logger.warning("Rate limit exceeded", 
                             period=period.value,
                             current=usage,
                             limit=limit,
                             requested=task_count,
                             reset_at=window_end.isoformat())
                
                # Record rate limit exceeded metric (avoid circular import)
                try:
                    from .metrics import metrics
                    metrics.record_rate_limit_exceeded(period.value)
                except ImportError:
                    pass  # Metrics not available
                
                return RateLimitResult(
                    allowed=False,
                    period_exceeded=period.value,
                    current_usage=current_usage,
                    limits={k.value: v for k, v in self.limits.items() if v > 0},
                    reset_times=reset_times
                )
        
        # All limits passed
        return RateLimitResult(
            allowed=True,
            current_usage=current_usage,
            limits={k.value: v for k, v in self.limits.items() if v > 0},
            reset_times=reset_times
        )
    
    async def record_completed_tasks(self, task_count: int, task_type: str = "unknown", task_ids: List[str] = None):
        """
        Record completed tasks for rate limiting tracking.
        Updates both in-memory and database counters.
        """
        if not settings.rate_limit_enabled:
            return
        
        await self.initialize()
        
        now = datetime.now(timezone.utc)
        
        # Update in-memory counters
        self._minute_counter += task_count
        self._hour_counter += task_count
        
        # Record in database for long-term tracking
        async with aiosqlite.connect(self.db_path) as db:
            # Insert task completion records for rolling windows
            if task_ids:
                for task_id in task_ids:
                    await db.execute("""
                        INSERT INTO task_completions (completed_at, task_type, task_id)
                        VALUES (?, ?, ?)
                    """, (now.isoformat(), task_type, task_id))
            else:
                # Bulk insert for multiple tasks without individual IDs
                for _ in range(task_count):
                    await db.execute("""
                        INSERT INTO task_completions (completed_at, task_type, task_id)
                        VALUES (?, ?, ?)
                    """, (now.isoformat(), task_type, None))
            
            # Update fixed window counters for day/week/month
            for period in [RateLimitPeriod.DAY, RateLimitPeriod.WEEK, RateLimitPeriod.MONTH]:
                limit = self.limits[period]
                if limit <= 0:  # Disabled
                    continue
                
                window_start, window_end = self._get_window_boundaries(period, now)
                
                await db.execute("""
                    INSERT OR REPLACE INTO rate_limits 
                    (time_period, current_count, window_start, window_end, last_updated)
                    VALUES (?, 
                            COALESCE((SELECT current_count FROM rate_limits 
                                    WHERE time_period = ? AND window_start <= ? AND window_end > ?), 0) + ?,
                            ?, ?, ?)
                """, (period.value, period.value, now.isoformat(), now.isoformat(), 
                      task_count, window_start.isoformat(), window_end.isoformat(), now.isoformat()))
            
            await db.commit()
        
        logger.debug("Recorded completed tasks", 
                    task_count=task_count, 
                    task_type=task_type,
                    timestamp=now.isoformat())
    
    async def get_current_usage(self) -> Dict[str, Usage]:
        """Get current usage statistics for all configured periods"""
        if not settings.rate_limit_enabled:
            return {}
        
        await self.initialize()
        
        now = datetime.now(timezone.utc)
        usage_stats = {}
        
        for period, limit in self.limits.items():
            if limit <= 0:  # Disabled
                continue
            
            # Get current usage
            if period in [RateLimitPeriod.MINUTE, RateLimitPeriod.HOUR]:
                current = await self._get_current_usage_in_memory(period, now)
            else:
                current = await self._get_current_usage_database(period, now)
            
            window_start, window_end = self._get_window_boundaries(period, now)
            
            usage_stats[period.value] = Usage(
                current=current,
                limit=limit,
                remaining=max(0, limit - current),
                reset_at=window_end,
                window_start=window_start
            )
        
        return usage_stats
    
    async def cleanup_old_records(self):
        """Clean up old task completion records to prevent database growth"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=35)  # Keep 35 days
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM task_completions WHERE completed_at < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            await db.commit()
            
            if deleted_count > 0:
                logger.info("Cleaned up old task completion records", deleted_count=deleted_count)


# Global rate limiter instance
rate_limiter = RateLimiter()