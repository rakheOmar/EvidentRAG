from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from qdrant_client import QdrantClient
from redis import Redis
import psycopg2


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="EvidentRAG", lifespan=lifespan)


@app.get("/health")
def health():
    checks = {}

    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "evidentrag"),
            password=os.getenv("POSTGRES_PASSWORD", "evidentrag"),
            dbname=os.getenv("POSTGRES_DB", "evidentrag"),
        )
        conn.close()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    try:
        qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))
        qdrant.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    try:
        r = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    return {"status": "ok", "checks": checks}
