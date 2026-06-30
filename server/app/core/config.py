from __future__ import annotations

from dataclasses import dataclass
import os


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_embedding_model(model: str) -> str:
    if "/" in model:
        return model
    if model.startswith("gemini-"):
        return f"google/{model}"
    return model


@dataclass(frozen=True)
class EmbeddingSettings:
    api_base: str
    api_key: str | None
    seed_demo_data: bool
    model: str
    dimensions: int


@dataclass(frozen=True)
class LLMSettings:
    api_base: str
    api_key: str | None
    generation_model: str
    utility_model: str


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    password: str | None
    db: str


@dataclass(frozen=True)
class QdrantSettings:
    url: str
    evidence_collection: str


@dataclass(frozen=True)
class RedisSettings:
    url: str


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    log_level: str
    log_format: str
    otel_enabled: bool
    otel_service_name: str
    otel_exporter_otlp_endpoint: str | None
    otel_exporter_otlp_headers: str | None
    otel_exporter_otlp_protocol: str
    otel_excluded_urls: str
    embeddings: EmbeddingSettings
    llm: LLMSettings
    db: DatabaseSettings
    qdrant: QdrantSettings
    redis: RedisSettings


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Server Scaffold"),
        environment=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("LOG_FORMAT", "json").lower(),
        otel_enabled=_get_bool("OTEL_ENABLED", False),
        otel_service_name=os.getenv("OTEL_SERVICE_NAME", "server-scaffold"),
        otel_exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        otel_exporter_otlp_headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
        otel_exporter_otlp_protocol=os.getenv(
            "OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"
        ).lower(),
        otel_excluded_urls=os.getenv("OTEL_EXCLUDED_URLS", "/health"),
        embeddings=EmbeddingSettings(
            api_base=os.getenv("LLM_API_BASE", "http://optiplex-3020:8081/v1"),
            api_key=os.getenv("LLM_API_KEY"),
            seed_demo_data=_get_bool("SEED_DEMO_DATA", False),
            model=_normalize_embedding_model(
                os.getenv("GEMINI_EMBEDDING_MODEL", "google/gemini-embedding-2")
            ),
            dimensions=int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768")),
        ),
        llm=LLMSettings(
            api_base=os.getenv("LLM_API_BASE", "http://optiplex-3020:8081/v1"),
            api_key=os.getenv("LLM_API_KEY"),
            generation_model=os.getenv("GENERATION_MODEL", "gemini-2.5-pro"),
            utility_model=os.getenv("UTILITY_MODEL", "gemini-2.5-flash"),
        ),
        db=DatabaseSettings(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "evidentrag"),
            password=os.getenv("POSTGRES_PASSWORD"),
            db=os.getenv("POSTGRES_DB", "evidentrag"),
        ),
        qdrant=QdrantSettings(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            evidence_collection=os.getenv(
                "EVIDENCE_COLLECTION_NAME", "evidentrag_evidence"
            ),
        ),
        redis=RedisSettings(
            url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        ),
    )
