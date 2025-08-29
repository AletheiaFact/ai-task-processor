from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional
from enum import Enum


class ProcessingMode(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    HYBRID = "hybrid"  # Ollama first, OpenAI fallback


class RateLimitStrategy(str, Enum):
    ROLLING = "rolling"  # Last N seconds/minutes/hours
    FIXED = "fixed"      # Calendar-based windows


class Settings(BaseSettings):
    api_base_url: str = Field(..., env="API_BASE_URL")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    polling_interval_seconds: int = Field(30, env="POLLING_INTERVAL_SECONDS")
    concurrency_limit: int = Field(5, env="CONCURRENCY_LIMIT")
    max_retries: int = Field(3, env="MAX_RETRIES")
    metrics_port: int = Field(8001, env="METRICS_PORT")
    
    request_timeout: int = Field(30, env="REQUEST_TIMEOUT")
    openai_timeout: int = Field(60, env="OPENAI_TIMEOUT")
    retry_backoff_factor: float = Field(2.0, env="RETRY_BACKOFF_FACTOR")
    circuit_breaker_threshold: int = Field(5, env="CIRCUIT_BREAKER_THRESHOLD")
    
    # Processing mode configuration
    processing_mode: ProcessingMode = Field(ProcessingMode.OPENAI, env="PROCESSING_MODE")
    
    # Ollama configuration
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_timeout: int = Field(120, env="OLLAMA_TIMEOUT")
    ollama_max_retries: int = Field(3, env="OLLAMA_MAX_RETRIES")
    ollama_model_download_timeout: int = Field(600, env="OLLAMA_MODEL_DOWNLOAD_TIMEOUT")
    
    # Ory Cloud OAuth2 Configuration
    ory_project_slug: str = Field(..., env="ORY_PROJECT_SLUG")
    oauth2_client_id: str = Field(..., env="OAUTH2_CLIENT_ID")
    oauth2_client_secret: str = Field(..., env="OAUTH2_CLIENT_SECRET")
    oauth2_scope: str = Field("read write", env="OAUTH2_SCOPE")
    
    @property
    def hydra_admin_url(self) -> str:
        return f"https://{self.ory_project_slug}.projects.oryapis.com/admin"
    
    @property
    def hydra_public_url(self) -> str:
        return f"https://{self.ory_project_slug}.projects.oryapis.com"
    
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # Rate Limiting Configuration
    rate_limit_enabled: bool = Field(True, env="RATE_LIMIT_ENABLED")
    rate_limit_strategy: RateLimitStrategy = Field(RateLimitStrategy.ROLLING, env="RATE_LIMIT_STRATEGY")
    rate_limit_storage_path: str = Field("/app/data/rate_limits.db", env="RATE_LIMIT_STORAGE_PATH")
    
    # Time-based limits (0 = disabled)
    rate_limit_per_minute: int = Field(0, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(0, env="RATE_LIMIT_PER_HOUR") 
    rate_limit_per_day: int = Field(0, env="RATE_LIMIT_PER_DAY")
    rate_limit_per_week: int = Field(0, env="RATE_LIMIT_PER_WEEK")
    rate_limit_per_month: int = Field(0, env="RATE_LIMIT_PER_MONTH")
    
    @field_validator('rate_limit_storage_path')
    @classmethod
    def validate_storage_path(cls, v):
        """Ensure storage directory exists for file paths"""
        import os
        if v != ":memory:" and not v.startswith(":"):
            try:
                os.makedirs(os.path.dirname(v), exist_ok=True)
            except (OSError, ValueError):
                pass  # Ignore permission errors for now
        return v
    
    class Config:
        env_file = ".env"


settings = Settings()