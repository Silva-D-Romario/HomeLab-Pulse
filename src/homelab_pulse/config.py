from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HomeLab Pulse"
    app_environment: str = "development"
    app_version: str = "0.9.1"
    database_url: str = "sqlite+aiosqlite:///./homelab_pulse.db"
    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "homelab-pulse"
    jwt_audience: str = "homelab-pulse-api"
    jwt_access_token_minutes: int = 30
    monitor_timeout_seconds: float = 10.0
    agent_token: str = "change-this-agent-token"
    docker_api_url: str = "http://docker-proxy:2375"
    redis_url: str = "redis://localhost:6379/0"
    api_base_url: str = "http://localhost:8000"
    dashboard_port: int = 8050
    credential_encryption_secret: str = "change-this-credential-secret"
    monitor_interval_seconds: int = 60

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_environment.lower() not in {"production", "prod"}:
            return self

        secrets = {
            "JWT_SECRET": self.jwt_secret,
            "CREDENTIAL_ENCRYPTION_SECRET": self.credential_encryption_secret,
        }
        invalid = [
            name
            for name, value in secrets.items()
            if len(value) < 32 or "change" in value.lower() or "development" in value.lower()
        ]
        if invalid:
            names = ", ".join(invalid)
            raise ValueError(f"Production requires strong secrets: {names}")
        if self.database_url.startswith("sqlite"):
            raise ValueError("Production requires a persistent database")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
