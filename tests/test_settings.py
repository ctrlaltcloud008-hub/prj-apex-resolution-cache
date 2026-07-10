"""Settings selection and fail-fast validation."""

from __future__ import annotations

import pytest

from resolution_cache.settings import Settings


def test_local_needs_no_production_settings(monkeypatch):
    for key in ("SPANNER_PROJECT_ID", "REDIS_URL", "PUSH_AUDIENCE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENV", "local")
    settings = Settings.from_env()
    assert settings.use_gcp is False
    assert settings.auth_required is False


def test_production_fails_fast_on_missing_settings(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    for key in (
        "SPANNER_PROJECT_ID",
        "SPANNER_INSTANCE_ID",
        "SPANNER_DATABASE_ID",
        "REDIS_URL",
        "PUSH_AUDIENCE",
        "PUSH_SERVICE_ACCOUNT",
        "GOOGLE_CLOUD_PROJECT",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="missing required production"):
        Settings.from_env()
