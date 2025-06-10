"""
Configuration management for AI Game Generator backend.
Handles environment variables, validation, and application settings.
"""

# Standard library imports
from functools import lru_cache
from typing import List, Optional, Set

# Third-party imports
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Core application settings."""

    model_config = SettingsConfigDict(env_prefix="")

    app_name: str = "AI Game Generator"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1

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

    model_config = SettingsConfigDict(env_prefix="")

    secret_key: str = "development-key-not-for-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v


class OpenAISettings(BaseSettings):
    """OpenAI API configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: str = "sk-placeholder-set-your-openai-key"
    model: str = "gpt-4-1106-preview"
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30

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

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    url: Optional[str] = None
    session_ttl: int = 3600
    cache_ttl: int = 1800

    @property
    def connection_url(self) -> str:
        """Generate Redis connection URL."""
        if self.url:
            return self.url

        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class SessionSettings(BaseSettings):
    """Session management configuration."""

    model_config = SettingsConfigDict(env_prefix="SESSION_")

    ttl: int = 3600
    max_sessions_per_ip: int = 10


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")

    requests: int = 100
    window: int = 60
    max_message_length: int = 5000
    max_conversation_history: int = 50


class GameSettings(BaseSettings):
    """Game generation limits and configuration."""

    model_config = SettingsConfigDict(env_prefix="")

    max_game_size: int = 1048576  # 1MB
    max_generation_time: int = 60
    max_concurrent_generations: int = 5

    @property
    def max_size(self) -> int:
        """Backward compatibility property."""
        return self.max_game_size


class WebSocketSettings(BaseSettings):
    """WebSocket configuration."""

    model_config = SettingsConfigDict(env_prefix="WS_")

    heartbeat_interval: int = 30
    max_connections: int = 1000


class CORSSettings(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(env_prefix="CORS_")

    origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    credentials: bool = True
    methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    headers: List[str] = ["*"]

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

    model_config = SettingsConfigDict(env_prefix="")

    sentry_dsn: Optional[str] = None
    prometheus_enabled: bool = False
    structured_logging: bool = True


class CodeValidationSettings(BaseSettings):
    """Code validation and security settings."""

    model_config = SettingsConfigDict(env_prefix="CODE_VALIDATION_")

    enabled: bool = True
    allowed_domains: Set[str] = {"localhost"}
    blocked_keywords: Set[str] = {"eval", "exec", "import os", "import sys"}

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

    model_config = SettingsConfigDict(env_prefix="")

    max_memory_usage: int = 512  # MB
    request_timeout: int = 30
    db_pool_size: int = 10


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
