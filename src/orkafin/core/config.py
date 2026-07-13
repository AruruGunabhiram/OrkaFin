"""Validated local runtime configuration."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Runtime environments recognized by the local service."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


LoopbackOrigins = Annotated[tuple[str, ...], NoDecode]


class Settings(BaseSettings):
    """Server-side configuration with intentionally safe local defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ORKAFIN_",
        extra="ignore",
        frozen=True,
    )

    application_name: str = "OrkaFin Local V1"
    service_name: str = "orkafin"
    api_version: str = "v1"
    environment: AppEnvironment = AppEnvironment.LOCAL
    database_url: str = "sqlite:///./orkafin.db"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    allowed_origins: LoopbackOrigins = ("http://127.0.0.1:8000", "http://localhost:8000")
    cors_allow_credentials: bool = False
    accept_incoming_request_ids: bool = True
    ai_provider: Literal["deterministic", "external"] = "deterministic"
    ai_provider_api_key: SecretStr | None = None
    confirmation_ttl_seconds: int = Field(default=300, ge=60, le=3600)
    fixture_mode: bool = True
    debug: bool = False

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
        elif isinstance(value, (list, tuple)) and all(isinstance(origin, str) for origin in value):
            origins = tuple(value)
        else:
            raise ValueError(
                "allowed_origins must be a comma-separated string or sequence of strings"
            )

        if not origins:
            raise ValueError("allowed_origins must contain at least one origin")
        return origins

    @field_validator("allowed_origins")
    @classmethod
    def require_loopback_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        for origin in origins:
            parsed = urlparse(origin)
            if origin == "*":
                raise ValueError("wildcard CORS origins are not allowed")
            if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                raise ValueError("allowed_origins must use explicit loopback origins")
            if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ValueError("allowed_origins must not contain a path, query, or fragment")
        return origins

    @model_validator(mode="after")
    def validate_local_security(self) -> Settings:
        if self.environment is AppEnvironment.PRODUCTION:
            raise ValueError("OrkaFin Local V1 cannot run in the production environment")
        if not self.database_url.startswith("sqlite://"):
            raise ValueError("OrkaFin Local V1 requires a SQLite database URL")
        if self.ai_provider == "external" and not self._has_provider_key():
            raise ValueError("an external AI provider requires a server-side API key")
        if self.cors_allow_credentials and "*" in self.allowed_origins:
            raise ValueError("credentialed CORS cannot use a wildcard origin")
        if self.debug and self.environment not in {
            AppEnvironment.LOCAL,
            AppEnvironment.DEVELOPMENT,
            AppEnvironment.TEST,
        }:
            raise ValueError("debug mode is limited to local development environments")
        return self

    def _has_provider_key(self) -> bool:
        return bool(
            self.ai_provider_api_key and self.ai_provider_api_key.get_secret_value().strip()
        )


def default_settings() -> Settings:
    """Build settings from the local environment when an app is constructed."""
    return Settings()
