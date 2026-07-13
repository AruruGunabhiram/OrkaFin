"""Minimal settings boundary; Prompt 3 adds environment parsing and validation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Safe defaults that let the local scaffold start without external secrets."""

    application_name: str = "OrkaFin Local V1"
    service_name: str = "orkafin"
    api_version: str = "v1"


def default_settings() -> Settings:
    """Return a fresh immutable settings value for a local application instance."""
    return Settings()
