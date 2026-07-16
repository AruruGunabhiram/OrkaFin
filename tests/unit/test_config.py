import pytest
from pydantic import ValidationError

from orkafin.core.config import AppEnvironment, Settings
from orkafin.providers.deterministic import DeterministicResponseProvider
from orkafin.providers.factory import build_response_provider


def test_settings_read_prefixed_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKAFIN_LOG_LEVEL", "debug")
    monkeypatch.setenv("ORKAFIN_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000")

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.allowed_origins == ("http://localhost:3000", "http://127.0.0.1:8000")


def test_deterministic_mode_does_not_require_an_api_key() -> None:
    settings = Settings(ai_provider="deterministic", ai_provider_api_key=None)

    assert settings.ai_provider == "deterministic"
    assert settings.ai_provider_api_key is None


def test_external_provider_requires_a_server_side_api_key() -> None:
    with pytest.raises(ValidationError, match="requires a server-side API key"):
        Settings(ai_provider="external")


def test_external_provider_requires_a_model_name() -> None:
    with pytest.raises(ValidationError, match="requires a model name"):
        Settings(ai_provider="external", ai_provider_api_key="server-only-key")


def test_default_settings_select_the_offline_deterministic_provider() -> None:
    assert isinstance(build_response_provider(Settings()), DeterministicResponseProvider)


def test_wildcard_credentialed_cors_is_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard CORS origins"):
        Settings(allowed_origins=("*",), cors_allow_credentials=True)


def test_production_environment_is_rejected_for_the_local_service() -> None:
    with pytest.raises(ValidationError, match="cannot run in the production"):
        Settings(environment=AppEnvironment.PRODUCTION)


def test_local_fixture_subject_requires_fixture_mode() -> None:
    with pytest.raises(ValidationError, match="requires fixture_mode"):
        Settings(fixture_mode=False, local_fixture_subject="limited_viewer")
