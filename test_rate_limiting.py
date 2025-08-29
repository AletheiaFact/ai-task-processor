#!/usr/bin/env python3
"""
Test script for multi-tier rate limiting functionality
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add the ai_task_processor to the Python path
sys.path.insert(0, '/home/caneppelevitor/development/aletheia-ai-task-manager')

from ai_task_processor.services.rate_limiter import rate_limiter
from ai_task_processor.config import settings

async def test_rate_limiter():
    print("🧪 Testing Multi-Tier Rate Limiting System")
    print("=" * 50)
    
    # Test 1: Database Initialization
    print("\n1️⃣ Testing Database Initialization...")
    try:
        await rate_limiter.initialize()
        print("✅ Database initialized successfully")
        print(f"📁 Database path: {rate_limiter.db_path}")
        print(f"⚙️  Strategy: {rate_limiter.strategy.value}")
        print(f"🎛️  Configured limits: {[(k.value, v) for k, v in rate_limiter.limits.items() if v > 0]}")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return
    
    # Test 2: Check Initial Usage (should be zero)
    print("\n2️⃣ Testing Initial Usage Check...")
    try:
        usage_stats = await rate_limiter.get_current_usage()
        print("✅ Usage statistics retrieved:")
        for period, usage in usage_stats.items():
            print(f"   {period}: {usage.current}/{usage.limit} (remaining: {usage.remaining})")
    except Exception as e:
        print(f"❌ Usage check failed: {e}")
        return
    
    # Test 3: Check All Limits (should pass initially)
    print("\n3️⃣ Testing Rate Limit Check...")
    try:
        result = await rate_limiter.check_all_limits(task_count=3)
        if result.allowed:
            print("✅ Rate limit check passed - 3 tasks allowed")
            print(f"   Current usage: {result.current_usage}")
        else:
            print(f"❌ Rate limit check failed: {result.period_exceeded}")
    except Exception as e:
        print(f"❌ Rate limit check error: {e}")
        return
    
    # Test 4: Record Some Tasks
    print("\n4️⃣ Testing Task Recording...")
    try:
        await rate_limiter.record_completed_tasks(
            task_count=3, 
            task_type="test_task",
            task_ids=["test-1", "test-2", "test-3"]
        )
        print("✅ Recorded 3 completed tasks")
        
        # Check updated usage
        usage_stats = await rate_limiter.get_current_usage()
        print("📊 Updated usage statistics:")
        for period, usage in usage_stats.items():
            print(f"   {period}: {usage.current}/{usage.limit} (remaining: {usage.remaining})")
    except Exception as e:
        print(f"❌ Task recording failed: {e}")
        return
    
    # Test 5: Test Rate Limiting (try to exceed minute limit)
    print("\n5️⃣ Testing Rate Limit Enforcement...")
    try:
        # Record 2 more tasks (total should be 5, which is our minute limit)
        await rate_limiter.record_completed_tasks(
            task_count=2, 
            task_type="test_task",
            task_ids=["test-4", "test-5"]
        )
        
        # Now try to exceed the limit
        result = await rate_limiter.check_all_limits(task_count=1)
        if result.allowed:
            print("⚠️  Rate limit check passed - this is unexpected if minute limit is 5")
        else:
            print(f"✅ Rate limit properly enforced - exceeded {result.period_exceeded}")
            print(f"   Current usage: {result.current_usage}")
            print(f"   Configured limits: {result.limits}")
    except Exception as e:
        print(f"❌ Rate limit enforcement test failed: {e}")
    
    # Test 6: Test Different Task Counts
    print("\n6️⃣ Testing Different Batch Sizes...")
    try:
        test_counts = [1, 3, 10]
        for count in test_counts:
            result = await rate_limiter.check_all_limits(task_count=count)
            status = "✅ ALLOWED" if result.allowed else f"❌ BLOCKED ({result.period_exceeded})"
            print(f"   {count} tasks: {status}")
    except Exception as e:
        print(f"❌ Batch size test failed: {e}")
    
    print("\n🏁 Rate Limiting Tests Complete!")

async def test_configuration():
    print("\n⚙️ Configuration Test")
    print("=" * 30)
    
    print(f"Rate Limiting Enabled: {settings.rate_limit_enabled}")
    print(f"Strategy: {settings.rate_limit_strategy.value}")
    print(f"Storage Path: {settings.rate_limit_storage_path}")
    
    print("\nConfigured Limits:")
    print(f"  Per Minute: {settings.rate_limit_per_minute}")
    print(f"  Per Hour: {settings.rate_limit_per_hour}")
    print(f"  Per Day: {settings.rate_limit_per_day}")
    print(f"  Per Week: {settings.rate_limit_per_week}")
    print(f"  Per Month: {settings.rate_limit_per_month}")

if __name__ == "__main__":
    asyncio.run(test_configuration())
    asyncio.run(test_rate_limiter())