"""Configuration-selected provider construction kept out of HTTP and retrieval layers."""

from __future__ import annotations

from orkafin.core.config import Settings
from orkafin.providers.base import ResponseProvider
from orkafin.providers.deterministic import DeterministicResponseProvider
from orkafin.providers.external import OpenAICompatibleResponseProvider


def build_response_provider(settings: Settings) -> ResponseProvider:
    """Return the offline default or the explicitly configured optional adapter."""
    if settings.ai_provider == "deterministic":
        return DeterministicResponseProvider()
    api_key = settings.ai_provider_api_key
    if api_key is None:  # Defensive; Settings rejects this combination.
        raise ValueError("external response provider requires a server-side API key")
    return OpenAICompatibleResponseProvider(
        api_key=api_key,
        base_url=settings.ai_provider_base_url,
        model=settings.ai_provider_model,
        timeout_seconds=settings.ai_provider_timeout_seconds,
    )
