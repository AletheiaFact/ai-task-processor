import httpx
import asyncio
import time
from typing import List, Optional, Dict, Any
from ..models import Task, TaskResult, TaskStatus
from ..config import settings
from ..utils import get_logger, retry, RetryableError, NonRetryableError
from .metrics import metrics

logger = get_logger(__name__)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                metrics.set_circuit_breaker_state("api", 2)
            else:
                raise NonRetryableError("Circuit breaker is open")
        
        try:
            result = await func()
            if self.state == "half-open":
                self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            metrics.set_circuit_breaker_state("api", 1)
            logger.warning("Circuit breaker opened", failure_count=self.failure_count)
    
    def reset(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        metrics.set_circuit_breaker_state("api", 0)
        logger.info("Circuit breaker reset")


class APIClient:
    def __init__(self):
        self.base_url = settings.api_base_url.rstrip('/')
        self.timeout = httpx.Timeout(settings.request_timeout)
        self.circuit_breaker = CircuitBreaker(settings.circuit_breaker_threshold)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    @retry(
        retryable_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
        non_retryable_exceptions=(NonRetryableError,)
    )
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        if not self._client:
            raise RuntimeError("APIClient not initialized. Use as async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        async def request():
            response = await self._client.request(method, url, **kwargs)
            
            if response.status_code >= 500:
                raise RetryableError(f"Server error: {response.status_code}")
            elif response.status_code >= 400:
                raise NonRetryableError(f"Client error: {response.status_code}")
            
            return response
        
        try:
            response = await self.circuit_breaker.call(request)
            duration = time.time() - start_time
            metrics.record_api_request(endpoint, method, response.status_code, duration)
            return response
        except Exception as e:
            duration = time.time() - start_time
            status_code = getattr(e, 'response', {}).get('status_code', 0)
            metrics.record_api_request(endpoint, method, status_code, duration)
            raise
    
    async def get_pending_tasks(self, limit: int = 10) -> List[Task]:
        response = await self._make_request(
            "GET",
            "/api/ai-tasks/pending",
            params={"limit": limit}
        )
        
        tasks_data = response.json()
        return [Task(**task_data) for task_data in tasks_data]
    
    async def update_task_status(self, task_id: str, result: TaskResult) -> bool:
        try:
            response = await self._make_request(
                "PATCH",
                f"/api/ai-tasks/{task_id}",
                json={
                    "status": result.status.value,
                    "output_data": result.output_data,
                    "error_message": result.error_message
                }
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(
                "Failed to update task status",
                task_id=task_id,
                error=str(e)
            )
            return False