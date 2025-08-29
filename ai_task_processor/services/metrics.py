from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any
import time

tasks_processed_total = Counter(
    'ai_tasks_processed_total',
    'Total number of AI tasks processed',
    ['task_type', 'status']
)

task_processing_duration_seconds = Histogram(
    'ai_task_processing_duration_seconds',
    'Time spent processing AI tasks',
    ['task_type']
)

tasks_in_flight = Gauge(
    'ai_tasks_in_flight',
    'Number of tasks currently being processed'
)

api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests made',
    ['endpoint', 'method', 'status_code']
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'Duration of API requests',
    ['endpoint', 'method']
)

openai_requests_total = Counter(
    'openai_requests_total',
    'Total number of OpenAI API requests',
    ['model', 'status']
)

openai_tokens_used = Counter(
    'openai_tokens_used_total',
    'Total number of OpenAI tokens used',
    ['model', 'type']
)

ollama_requests_total = Counter(
    'ollama_requests_total',
    'Total number of Ollama API requests',
    ['model', 'status']
)

ollama_tokens_used = Counter(
    'ollama_tokens_used_total',
    'Total number of Ollama tokens used (estimated)',
    ['model', 'type']
)

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service']
)

# Rate limiting metrics
rate_limit_current_usage = Gauge(
    'rate_limit_current_usage',
    'Current usage count for time period',
    ['period']
)

rate_limit_max_allowed = Gauge(
    'rate_limit_max_allowed', 
    'Maximum allowed tasks for time period',
    ['period']
)

rate_limit_exceeded_total = Counter(
    'rate_limit_exceeded_total',
    'Total number of rate limit exceeded events',
    ['period']
)

rate_limit_check_duration_seconds = Histogram(
    'rate_limit_check_duration_seconds',
    'Time spent checking rate limits'
)

rate_limit_remaining = Gauge(
    'rate_limit_remaining',
    'Remaining tasks allowed in current window',
    ['period']
)


class MetricsCollector:
    def __init__(self):
        self._start_times: Dict[str, float] = {}
    
    def start_task_processing(self, task_id: str, task_type: str):
        self._start_times[task_id] = time.time()
        tasks_in_flight.inc()
    
    def end_task_processing(self, task_id: str, task_type: str, status: str):
        if task_id in self._start_times:
            duration = time.time() - self._start_times[task_id]
            task_processing_duration_seconds.labels(task_type=task_type).observe(duration)
            del self._start_times[task_id]
        
        tasks_processed_total.labels(task_type=task_type, status=status).inc()
        tasks_in_flight.dec()
    
    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        api_requests_total.labels(
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).inc()
        api_request_duration_seconds.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)
    
    def record_openai_request(self, model: str, status: str, usage: Dict[str, Any] = None):
        openai_requests_total.labels(model=model, status=status).inc()
        
        if usage:
            for token_type, count in usage.items():
                openai_tokens_used.labels(
                    model=model,
                    type=token_type
                ).inc(count)
    
    def record_ollama_request(self, model: str, status: str, usage: Dict[str, Any] = None):
        ollama_requests_total.labels(model=model, status=status).inc()
        
        if usage:
            for token_type, count in usage.items():
                ollama_tokens_used.labels(
                    model=model,
                    type=token_type
                ).inc(count)
    
    def set_circuit_breaker_state(self, service: str, state: int):
        circuit_breaker_state.labels(service=service).set(state)
    
    def record_rate_limit_exceeded(self, period: str):
        """Record when a rate limit is exceeded for a specific period"""
        rate_limit_exceeded_total.labels(period=period).inc()
    
    def update_rate_limit_metrics(self, usage_stats: dict):
        """Update all rate limiting metrics with current usage statistics"""
        for period, usage in usage_stats.items():
            rate_limit_current_usage.labels(period=period).set(usage.current)
            rate_limit_max_allowed.labels(period=period).set(usage.limit)
            rate_limit_remaining.labels(period=period).set(usage.remaining)
    
    def observe_rate_limit_check_duration(self, duration: float):
        """Record time spent checking rate limits"""
        rate_limit_check_duration_seconds.observe(duration)


metrics = MetricsCollector()