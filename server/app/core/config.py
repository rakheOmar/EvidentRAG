from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import os
from dotenv import load_dotenv


_ENV_LOADED = False


def load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    root = Path(__file__).resolve().parents[3]
    env_name = ".env.docker" if Path("/.dockerenv").exists() else ".env.local"
    env_path = root / env_name
    if env_path.exists():
        load_dotenv(env_path, override=True)
    elif (root / ".env").exists():
        load_dotenv(root / ".env", override=True)
    else:
        load_dotenv(override=True)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_embedding_model(model: str) -> str:
    return model.removeprefix("google/")


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    environment: str
    client_dist_path: str


@dataclass(frozen=True)
class LogSettings:
    level: str
    format: str


@dataclass(frozen=True)
class OtelSettings:
    enabled: bool
    service_name: str
    exporter_otlp_endpoint: str | None
    exporter_otlp_headers: str | None
    exporter_otlp_protocol: str
    excluded_urls: str


@dataclass(frozen=True)
class LLMSettings:
    api_base: str
    api_key: str | None
    generation_model: str
    utility_model: str


@dataclass(frozen=True)
class EmbeddingSettings:
    api_base: str
    api_key: str | None
    seed_demo_data: bool
    model: str
    dimensions: int
    batch_size: int = 64


@dataclass(frozen=True)
class RerankerSettings:
    api_base: str
    api_key: str | None
    model: str


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
class IngestionSettings:
    storage_path: str
    max_upload_bytes: int
    retry_attempts: int
    audit_retention_days: int
    job_timeout_seconds: int = 900


@dataclass(frozen=True)
class RateLimitSettings:
    retry_window_seconds: float
    generation_requests_per_minute: int
    utility_requests_per_minute: int
    embedding_requests_per_minute: int
    rerank_requests_per_minute: int
    generation_concurrency: int
    utility_concurrency: int
    embedding_concurrency: int
    rerank_concurrency: int


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    log: LogSettings
    otel: OtelSettings
    llm: LLMSettings
    embeddings: EmbeddingSettings
    reranker: RerankerSettings
    db: DatabaseSettings
    qdrant: QdrantSettings
    redis: RedisSettings
    ingestion: IngestionSettings = field(
        default_factory=lambda: IngestionSettings(
            storage_path="./data/documents",
            max_upload_bytes=25 * 1024 * 1024,
            retry_attempts=3,
            audit_retention_days=7,
        )
    )
    rate_limits: RateLimitSettings = field(
        default_factory=lambda: RateLimitSettings(
            retry_window_seconds=60.0,
            generation_requests_per_minute=20,
            utility_requests_per_minute=60,
            embedding_requests_per_minute=60,
            rerank_requests_per_minute=10,
            generation_concurrency=2,
            utility_concurrency=4,
            embedding_concurrency=4,
            rerank_concurrency=2,
        )
    )


def get_settings() -> Settings:
    load_env()
    return Settings(
        app=AppSettings(
            app_name=os.getenv("APP_NAME", "Server Scaffold"),
            environment=os.getenv("APP_ENV", "development"),
            client_dist_path=os.getenv("CLIENT_DIST_PATH", "../client/dist"),
        ),
        log=LogSettings(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format=os.getenv("LOG_FORMAT", "json").lower(),
        ),
        otel=OtelSettings(
            enabled=_get_bool("OTEL_ENABLED", False),
            service_name=os.getenv("OTEL_SERVICE_NAME", "server-scaffold"),
            exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            exporter_otlp_headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
            exporter_otlp_protocol=os.getenv(
                "OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"
            ).lower(),
            excluded_urls=os.getenv("OTEL_EXCLUDED_URLS", "/health"),
        ),
        llm=LLMSettings(
            api_base=os.getenv("LLM_API_BASE", "http://optiplex-3020:8081/v1"),
            api_key=os.getenv("LLM_API_KEY"),
            generation_model=os.getenv("GENERATION_MODEL", "gemini-2.5-pro"),
            utility_model=os.getenv("UTILITY_MODEL", "gemini-2.5-flash"),
        ),
        embeddings=EmbeddingSettings(
            api_base=os.getenv(
                "GEMINI_API_BASE", "https://generativelanguage.googleapis.com"
            ),
            api_key=os.getenv("GEMINI_API_KEY"),
            seed_demo_data=_get_bool("SEED_DEMO_DATA", False),
            model=_normalize_embedding_model(
                os.getenv("GEMINI_EMBEDDING_MODEL", "google/gemini-embedding-2")
            ),
            dimensions=int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768")),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "64")),
        ),
        reranker=RerankerSettings(
            api_base=os.getenv("RERANKER_API_BASE", "https://api.cohere.com/v2"),
            api_key=os.getenv("RERANKER_API_KEY"),
            model=os.getenv("RERANKER_MODEL", "rerank-english-v3.0"),
        ),
        db=DatabaseSettings(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "evidentrag"),
            password=os.getenv("POSTGRES_PASSWORD", "evidentrag"),
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
        ingestion=IngestionSettings(
            storage_path=os.getenv("DOCUMENT_STORAGE_PATH", "./data/documents"),
            max_upload_bytes=int(
                os.getenv("MAX_DOCUMENT_UPLOAD_BYTES", str(25 * 1024 * 1024))
            ),
            retry_attempts=int(os.getenv("DOCUMENT_INGESTION_RETRY_ATTEMPTS", "3")),
            audit_retention_days=int(os.getenv("DOCUMENT_AUDIT_RETENTION_DAYS", "7")),
            job_timeout_seconds=int(
                os.getenv("DOCUMENT_INGESTION_TIMEOUT_SECONDS", "900")
            ),
        ),
        rate_limits=RateLimitSettings(
            retry_window_seconds=float(os.getenv("AI_RETRY_WINDOW_SECONDS", "60")),
            generation_requests_per_minute=int(
                os.getenv("LLM_GENERATION_REQUESTS_PER_MINUTE", "20")
            ),
            utility_requests_per_minute=int(
                os.getenv("LLM_UTILITY_REQUESTS_PER_MINUTE", "60")
            ),
            embedding_requests_per_minute=int(
                os.getenv("EMBEDDING_REQUESTS_PER_MINUTE", "60")
            ),
            rerank_requests_per_minute=int(
                os.getenv("RERANK_REQUESTS_PER_MINUTE", "10")
            ),
            generation_concurrency=int(os.getenv("LLM_GENERATION_CONCURRENCY", "2")),
            utility_concurrency=int(os.getenv("LLM_UTILITY_CONCURRENCY", "4")),
            embedding_concurrency=int(os.getenv("EMBEDDING_CONCURRENCY", "4")),
            rerank_concurrency=int(os.getenv("RERANK_CONCURRENCY", "2")),
        ),
    )
