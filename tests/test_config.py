"""Configuration is environment driven and validates its inputs."""

from __future__ import annotations

import pytest

from idp.config import Settings, get_settings


def test_defaults_are_production_safe() -> None:
    settings = Settings()
    assert settings.provider in {"vertex", "ollama"}
    assert settings.vertex_project_id == ""
    assert settings.max_retries >= 1


def test_invalid_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("IDP_PROVIDER", "chatgpt")
    with pytest.raises(ValueError, match="IDP_PROVIDER"):
        Settings.from_env()


def test_provider_is_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("IDP_PROVIDER", "vertex")
    monkeypatch.setenv("VERTEX_PROJECT_ID", "my-real-project")
    settings = Settings.from_env()
    assert settings.provider == "vertex"
    assert settings.vertex_configured() is True


def test_placeholder_project_id_is_not_considered_configured(monkeypatch) -> None:
    monkeypatch.setenv("VERTEX_PROJECT_ID", "your_id_project")
    assert Settings.from_env().vertex_configured() is False


def test_describe_never_exposes_a_secret() -> None:
    described = Settings().describe()
    assert "VERTEX_PROJECT_ID" not in described
    assert isinstance(described["provider"], str)


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()