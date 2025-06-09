"""
Configuration management for AI Game Generator backend.
Handles environment variables, validation, and application settings.
"""

# Standard library imports
import os
from functools import lru_cache
from typing import List, Optional, Set

# Third-party imports
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Core application settings."""

    app_name: str = Field(default="AI Game Generator", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=False, env="RELOAD")
    workers: int = Field(default=1, env="WORKERS")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        valid_envs = {"development", "staging", "production", "testing"}
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}")
        return v.lower()


class SecuritySettings(BaseSettings):
    """Security and authentication settings."""

    secret_key: str = Field(default="development-key-not-for-production", env="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    algorithm: str = Field(default="HS256", env="ALGORITHM")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v


class OpenAISettings(BaseSettings):
    """OpenAI API configuration."""

    api_key: str = Field(default="sk-placeholder-set-your-openai-key", env="OPENAI_API_KEY")
    model: str = Field(default="gpt-4-1106-preview", env="OPENAI_MODEL")
    max_tokens: int = Field(default=4000, env="OPENAI_MAX_TOKENS")
    temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    timeout: int = Field(default=30, env="OPENAI_TIMEOUT")

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v):
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v):
        if v < 100 or v > 8192:
            raise ValueError("Max tokens must be between 100 and 8192")
        return v


class RedisSettings(BaseSettings):
    """Redis configuration for caching and session storage."""

    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    url: Optional[str] = Field(default=None, env="REDIS_URL")
    session_ttl: int = Field(default=3600, env="REDIS_SESSION_TTL")
    cache_ttl: int = Field(default=1800, env="REDIS_CACHE_TTL")

    @property
    def connection_url(self) -> str:
        """Generate Redis connection URL."""
        if self.url:
            return self.url

        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class SessionSettings(BaseSettings):
    """Session management configuration."""

    ttl: int = Field(default=3600, env="SESSION_TTL")
    max_sessions_per_ip: int = Field(default=10, env="MAX_SESSIONS_PER_IP")


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    window: int = Field(default=60, env="RATE_LIMIT_WINDOW")
    max_message_length: int = Field(default=5000, env="MAX_MESSAGE_LENGTH")
    max_conversation_history: int = Field(default=50, env="MAX_CONVERSATION_HISTORY")


class GameSettings(BaseSettings):
    """Game generation limits and configuration."""

    max_size: int = Field(default=1048576, env="MAX_GAME_SIZE")  # 1MB
    max_generation_time: int = Field(default=60, env="MAX_GENERATION_TIME")
    max_concurrent_generations: int = Field(default=5, env="MAX_CONCURRENT_GENERATIONS")


class WebSocketSettings(BaseSettings):
    """WebSocket configuration."""

    heartbeat_interval: int = Field(default=30, env="WS_HEARTBEAT_INTERVAL")
    max_connections: int = Field(default=1000, env="WS_MAX_CONNECTIONS")


class CORSSettings(BaseSettings):
    """CORS configuration."""

    origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"], env="CORS_ORIGINS"
    )
    credentials: bool = Field(default=True, env="CORS_CREDENTIALS")
    methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"], env="CORS_METHODS"
    )
    headers: List[str] = Field(default=["*"], env="CORS_HEADERS")

    @field_validator("origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("methods", mode="before")
    @classmethod
    def parse_methods(cls, v):
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v


class MonitoringSettings(BaseSettings):
    """Monitoring and logging configuration."""

    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    prometheus_enabled: bool = Field(default=False, env="PROMETHEUS_ENABLED")
    structured_logging: bool = Field(default=True, env="STRUCTURED_LOGGING")


class TemplateSettings(BaseSettings):
    """Template management configuration."""

    cache_ttl: int = Field(default=3600, env="TEMPLATE_CACHE_TTL")
    validation_enabled: bool = Field(default=True, env="TEMPLATE_VALIDATION_ENABLED")


class CodeValidationSettings(BaseSettings):
    """Code validation and security settings."""

    enabled: bool = Field(default=True, env="CODE_VALIDATION_ENABLED")
    allowed_domains: Set[str] = Field(default={"localhost"}, env="ALLOWED_DOMAINS")
    blocked_keywords: Set[str] = Field(
        default={"eval", "exec", "import os", "import sys"}, env="BLOCKED_KEYWORDS"
    )

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def parse_allowed_domains(cls, v):
        if isinstance(v, str):
            return set(domain.strip() for domain in v.split(","))
        return set(v) if v else set()

    @field_validator("blocked_keywords", mode="before")
    @classmethod
    def parse_blocked_keywords(cls, v):
        if isinstance(v, str):
            return set(keyword.strip() for keyword in v.split(","))
        return set(v) if v else set()


class PerformanceSettings(BaseSettings):
    """Performance and resource limits."""

    max_memory_usage: int = Field(default=512, env="MAX_MEMORY_USAGE")  # MB
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")


class Settings:
    """Main settings container that combines all configuration sections."""

    def __init__(self):
        self.app = AppSettings()
        self.security = SecuritySettings()
        self.openai = OpenAISettings()
        self.redis = RedisSettings()
        self.session = SessionSettings()
        self.rate_limit = RateLimitSettings()
        self.game = GameSettings()
        self.websocket = WebSocketSettings()
        self.cors = CORSSettings()
        self.monitoring = MonitoringSettings()
        self.template = TemplateSettings()
        self.code_validation = CodeValidationSettings()
        self.performance = PerformanceSettings()

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.app.environment == "testing"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Export commonly used settings
settings = get_settings()
