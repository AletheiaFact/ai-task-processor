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

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service']
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
    
    def set_circuit_breaker_state(self, service: str, state: int):
        circuit_breaker_state.labels(service=service).set(state)


metrics = MetricsCollector()