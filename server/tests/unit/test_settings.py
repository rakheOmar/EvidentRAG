from __future__ import annotations

from app.core.config import get_settings


def test_settings_read_otel_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "EvidentRAG")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "evidentrag-server")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=token")
    monkeypatch.setenv("OTEL_EXCLUDED_URLS", "/health,/ping")

    settings = get_settings()

    assert settings.app.app_name == "EvidentRAG"
    assert settings.otel.enabled is True
    assert settings.otel.service_name == "evidentrag-server"
    assert settings.otel.exporter_otlp_endpoint == "http://collector:4317"
    assert settings.otel.exporter_otlp_headers == "authorization=token"
    assert settings.otel.excluded_urls == "/health,/ping"


def test_settings_read_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_BASE", "http://custom:8080/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-my-key")
    monkeypatch.setenv("GENERATION_MODEL", "my-gen-model")
    monkeypatch.setenv("UTILITY_MODEL", "my-util-model")

    settings = get_settings()

    assert settings.llm.api_base == "http://custom:8080/v1"
    assert settings.llm.api_key == "sk-my-key"
    assert settings.llm.generation_model == "my-gen-model"
    assert settings.llm.utility_model == "my-util-model"


def test_settings_normalize_shorthand_embedding_model(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")

    settings = get_settings()

    assert settings.embeddings.model == "google/gemini-embedding-2"


def test_settings_read_db_env(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "pg.example.com")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "admin")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "ragdb")

    settings = get_settings()

    assert settings.db.host == "pg.example.com"
    assert settings.db.port == 5433
    assert settings.db.user == "admin"
    assert settings.db.password == "secret"
    assert settings.db.db == "ragdb"


def test_settings_read_qdrant_env(monkeypatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("EVIDENCE_COLLECTION_NAME", "my_evidence")

    settings = get_settings()

    assert settings.qdrant.url == "http://qdrant:6333"
    assert settings.qdrant.evidence_collection == "my_evidence"


def test_settings_read_reranker_env(monkeypatch) -> None:
    monkeypatch.setenv("RERANKER_API_BASE", "https://custom-reranker.example.com")
    monkeypatch.setenv("RERANKER_API_KEY", "reranker-secret")
    monkeypatch.setenv("RERANKER_MODEL", "custom-reranker-v2")

    settings = get_settings()

    assert settings.reranker.api_base == "https://custom-reranker.example.com"
    assert settings.reranker.api_key == "reranker-secret"
    assert settings.reranker.model == "custom-reranker-v2"
