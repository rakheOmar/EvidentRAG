from __future__ import annotations

import pytest

from app.main import settings
from tests.conftest import (
    _destructive_schema_reset_enabled,
    _integration_settings,
    _is_disposable_database,
)


@pytest.mark.parametrize(
    ("database_name", "expected"),
    [
        pytest.param("evidentrag_test", True, id="test-suffix"),
        pytest.param("test_evidentrag", True, id="test-prefix"),
        pytest.param("evidentrag", False, id="development-database"),
        pytest.param("production-test", False, id="hyphenated-production-name"),
        pytest.param("contest", False, id="test-substring-only"),
    ],
)
def test_disposable_database_name_requires_a_test_segment(
    database_name: str, expected: bool
) -> None:
    assert _is_disposable_database(database_name) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("true", True, id="explicit-opt-in"),
        pytest.param("false", False, id="explicit-opt-out"),
        pytest.param("1", False, id="ambiguous-truthy-value"),
    ],
)
def test_destructive_schema_reset_requires_explicit_true(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("TEST_ALLOW_DESTRUCTIVE_SCHEMA_RESET", value)

    assert _destructive_schema_reset_enabled() is expected


def test_integration_settings_use_the_explicit_test_database(monkeypatch) -> None:
    monkeypatch.setenv("TEST_POSTGRES_DB", "evidentrag_test")
    monkeypatch.setenv("TEST_POSTGRES_PORT", "55432")
    monkeypatch.setenv("TEST_ALLOW_DESTRUCTIVE_SCHEMA_RESET", "true")

    integration_settings = _integration_settings(settings)

    assert integration_settings is not settings
    assert integration_settings.db.db == "evidentrag_test"
    assert integration_settings.db.port == 55432
    assert settings.db.db != integration_settings.db.db
