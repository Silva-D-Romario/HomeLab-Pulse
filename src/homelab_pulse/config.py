from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HomeLab Pulse"
    app_environment: str = "development"
    app_version: str = "0.4.0"
    database_url: str = "sqlite+aiosqlite:///./homelab_pulse.db"
    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 30
    monitor_timeout_seconds: float = 10.0
    agent_token: str = "change-this-agent-token"
    docker_api_url: str = "http://docker-proxy:2375"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
