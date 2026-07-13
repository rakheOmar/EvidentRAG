from __future__ import annotations

from app.core.config import (
    AppSettings,
    DatabaseSettings,
    EmbeddingSettings,
    LLMSettings,
    LogSettings,
    OtelSettings,
    QdrantSettings,
    RedisSettings,
    RerankerSettings,
    Settings,
)


def build_runtime_settings(
    *,
    seed_demo_data: bool = False,
    otel_enabled: bool = False,
    otel_protocol: str = "grpc",
) -> Settings:
    return Settings(
        app=AppSettings(
            app_name="EvidentRAG",
            environment="test",
            client_dist_path="../client/dist",
        ),
        log=LogSettings(level="INFO"),
        otel=OtelSettings(
            enabled=otel_enabled,
            service_name="evidentrag-test",
            exporter_otlp_endpoint="http://collector:4317",
            exporter_otlp_headers="authorization=token",
            exporter_otlp_protocol=otel_protocol,
            excluded_urls="/health",
        ),
        embeddings=EmbeddingSettings(
            api_base="http://embedding.test/v1",
            api_key=None,
            seed_demo_data=seed_demo_data,
            model="embed-test",
            dimensions=768,
        ),
        llm=LLMSettings(
            api_base="http://llm.test/v1",
            api_key=None,
            generation_model="llm-generation-test",
            utility_model="llm-utility-test",
        ),
        reranker=RerankerSettings(
            api_base="http://reranker.test/v2",
            api_key=None,
            model="rerank-test",
        ),
        db=DatabaseSettings(
            host="localhost",
            port=5432,
            user="evidentrag",
            password="evidentrag",
            db="evidentrag",
        ),
        qdrant=QdrantSettings(
            url="http://qdrant.test:6333",
            evidence_collection="evidentrag_evidence",
        ),
        redis=RedisSettings(url="redis://localhost:6379/0"),
    )
