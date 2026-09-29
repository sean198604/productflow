from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ProductFlow API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://productflow:not-configured@localhost:5432/productflow"
    database_admin_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:7030"

    storage_root: Path = Path("storage")
    max_upload_size_mb: int = Field(default=50, ge=1, le=1024)
    dependency_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    jwt_secret: str = Field(
        default="not-configured-set-JWT_SECRET-before-running",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "productflow"
    jwt_audience: str = "productflow-web"
    jwt_access_token_minutes: int = Field(default=30, ge=5, le=1440)

    initial_admin_enabled: bool = False
    initial_admin_tenant_name: str = "ProductFlow System"
    initial_admin_tenant_slug: str = "productflow-admin"
    initial_admin_username: str = "admin"
    initial_admin_email: str = "admin@productflow.local"
    initial_admin_password: str = Field(
        default="not-configured",
        min_length=12,
    )

    @model_validator(mode="after")
    def reject_unconfigured_secrets(self) -> "Settings":
        if self.jwt_secret.startswith("not-configured"):
            raise ValueError("JWT_SECRET must be configured")
        if (
            self.initial_admin_enabled
            and self.initial_admin_password == "not-configured"
        ):
            raise ValueError("INITIAL_ADMIN_PASSWORD must be configured when bootstrap is enabled")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
