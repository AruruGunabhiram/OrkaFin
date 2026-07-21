"""Validated local runtime configuration."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Runtime environments recognized by the local service."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AdapterMode(StrEnum):
    """OrkaATS adapter implementations available to this service."""

    MOCK = "mock"
    APPS_SCRIPT = "apps_script"


LoopbackOrigins = Annotated[tuple[str, ...], NoDecode]


class Settings(BaseSettings):
    """Server-side configuration with intentionally safe local defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ORKAFIN_",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    application_name: str = "OrkaFin Local V1"
    service_name: str = "orkafin"
    api_version: str = "v1"
    environment: AppEnvironment = AppEnvironment.LOCAL
    database_url: str = "sqlite:///./var/orkafin.db"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    allowed_origins: LoopbackOrigins = ("http://127.0.0.1:8000", "http://localhost:8000")
    cors_allow_credentials: bool = False
    accept_incoming_request_ids: bool = True
    ai_provider: Literal["deterministic", "external"] = "deterministic"
    ai_provider_api_key: SecretStr | None = None
    ai_provider_base_url: str = "https://api.openai.com/v1/chat/completions"
    ai_provider_model: str = ""
    ai_provider_timeout_seconds: float = Field(default=5.0, gt=0.0, le=30.0)
    confirmation_ttl_seconds: int = Field(default=300, ge=60, le=3600)
    recommendation_impression_window_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    recommendation_dismissal_suppression_seconds: int = Field(
        default=2_592_000, ge=60, le=31_536_000
    )
    recommendation_reduced_window_multiplier: int = Field(default=7, ge=2, le=30)
    adapter_mode: AdapterMode = Field(
        default=AdapterMode.MOCK,
        validation_alias=AliasChoices("ADAPTER_MODE", "ORKAFIN_ADAPTER_MODE"),
    )
    orka_ats_adapter_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ORKA_ATS_ADAPTER_URL", "ORKAFIN_ORKA_ATS_ADAPTER_URL"),
    )
    orka_ats_adapter_version: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices(
            "ORKA_ATS_ADAPTER_VERSION", "ORKAFIN_ORKA_ATS_ADAPTER_VERSION"
        ),
    )
    orka_ats_adapter_key_id: str = Field(
        default="orkaats-dev-1",
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("ORKA_ATS_ADAPTER_KEY_ID", "ORKAFIN_ORKA_ATS_ADAPTER_KEY_ID"),
    )
    orka_ats_adapter_shared_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ORKA_ATS_ADAPTER_SHARED_SECRET",
            "ORKAFIN_ORKA_ATS_ADAPTER_SHARED_SECRET",
        ),
    )
    fixture_mode: bool = True
    local_fixture_subject: str | None = None
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
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("allowed_origins must not contain user information")
            try:
                _ = parsed.port
            except ValueError as error:
                raise ValueError("allowed_origins must contain a valid port") from error
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
        if self.ai_provider == "external" and not self.ai_provider_model.strip():
            raise ValueError("an external AI provider requires a model name")
        if self.ai_provider == "external":
            parsed_provider_url = urlparse(self.ai_provider_base_url)
            if parsed_provider_url.scheme != "https" or not parsed_provider_url.netloc:
                raise ValueError("an external AI provider requires an HTTPS base URL")
        if self.cors_allow_credentials and "*" in self.allowed_origins:
            raise ValueError("credentialed CORS cannot use a wildcard origin")
        if self.debug and self.environment not in {
            AppEnvironment.LOCAL,
            AppEnvironment.DEVELOPMENT,
            AppEnvironment.TEST,
        }:
            raise ValueError("debug mode is limited to local development environments")
        if self.local_fixture_subject is not None and not self.fixture_mode:
            raise ValueError("a local fixture subject requires fixture_mode=true")
        if self.adapter_mode is AdapterMode.APPS_SCRIPT:
            self._validate_apps_script_settings()
        return self

    def _has_provider_key(self) -> bool:
        return bool(
            self.ai_provider_api_key and self.ai_provider_api_key.get_secret_value().strip()
        )

    def _validate_apps_script_settings(self) -> None:
        if self.orka_ats_adapter_url is None:
            raise ValueError("apps_script adapter mode requires ORKA_ATS_ADAPTER_URL")
        endpoint = self.orka_ats_adapter_url
        parsed = urlparse(endpoint)
        if endpoint != endpoint.strip() or parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("ORKA_ATS_ADAPTER_URL must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "ORKA_ATS_ADAPTER_URL must not contain credentials, query, or fragment"
            )
        if not parsed.path.endswith("/exec"):
            raise ValueError("ORKA_ATS_ADAPTER_URL must end in /exec")
        if not self.orka_ats_adapter_key_id.strip():
            raise ValueError("ORKA_ATS_ADAPTER_KEY_ID must not be blank")
        if self.orka_ats_adapter_shared_secret is None:
            raise ValueError("apps_script adapter mode requires ORKA_ATS_ADAPTER_SHARED_SECRET")
        secret = self.orka_ats_adapter_shared_secret.get_secret_value()
        if re.fullmatch(r"[0-9a-fA-F]{64}", secret) is None:
            raise ValueError("ORKA_ATS_ADAPTER_SHARED_SECRET must be 64 hexadecimal characters")


def default_settings() -> Settings:
    """Build settings from the local environment when an app is constructed."""
    return Settings()
