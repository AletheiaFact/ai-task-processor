from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


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
    
    class Config:
        env_file = ".env"


settings = Settings()