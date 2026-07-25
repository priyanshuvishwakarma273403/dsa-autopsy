"""Unit tests validating configuration loading and environment overrides."""

import pytest

from dsa_autopsy.config.settings import Settings


@pytest.mark.unit
def test_settings_default_values() -> None:
    """Validate that default settings load as expected when no environment variables are set."""
    settings = Settings()

    assert settings.ENV == "development"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.LOG_FORMAT == "text"
    assert settings.PARSER_ENGINE == "native_ast"
    assert settings.EXECUTION_TIMEOUT_SECS == 5
    assert settings.AI_PROVIDER == "mock"
    assert settings.AI_API_KEY is None


@pytest.mark.unit
def test_settings_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that Settings correctly registers environment overrides.

    Checks that variables prefixed with DSA_AUTOPSY_ are parsed.
    """
    monkeypatch.setenv("DSA_AUTOPSY_ENV", "production")
    monkeypatch.setenv("DSA_AUTOPSY_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DSA_AUTOPSY_LOG_FORMAT", "json")
    monkeypatch.setenv("DSA_AUTOPSY_EXECUTION_TIMEOUT_SECS", "10")
    monkeypatch.setenv("DSA_AUTOPSY_AI_API_KEY", "super-secret-key")

    settings = Settings()

    assert settings.ENV == "production"
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.LOG_FORMAT == "json"
    assert settings.EXECUTION_TIMEOUT_SECS == 10
    assert settings.AI_API_KEY is not None
    assert settings.AI_API_KEY.get_secret_value() == "super-secret-key"
