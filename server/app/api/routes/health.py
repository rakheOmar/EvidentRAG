from __future__ import annotations

from sqlalchemy import text

from fastapi import APIRouter, Request

router = APIRouter()


def _pg_host(db_settings) -> str:
    return f"{db_settings.host}:{db_settings.port}"


async def _check_postgres(request: Request) -> dict:
    try:
        async with request.app.state.engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name"
                )
            )
            tables = []
            for row in result:
                count = await conn.scalar(
                    text(f"SELECT COUNT(*) FROM {row[0]}")
                )
                tables.append({"name": row[0], "rows": count})
    except Exception as exc:
        return {
            "status": "unhealthy",
            "host": _pg_host(request.app.state.settings.db),
            "tables": [],
            "error": str(exc),
        }

    return {
        "status": "healthy",
        "host": _pg_host(request.app.state.settings.db),
        "tables": tables,
    }


async def _check_qdrant(request: Request) -> dict:
    try:
        client = request.app.state.qdrant_store._client
        collections_response = await client.get_collections()
        collections = []
        for col in collections_response.collections:
            info = await client.get_collection(col.name)
            collections.append({"name": col.name, "points": info.points_count})
    except Exception as exc:
        return {
            "status": "unhealthy",
            "url": request.app.state.settings.qdrant.url,
            "collections": [],
            "error": str(exc),
        }

    return {
        "status": "healthy",
        "url": request.app.state.settings.qdrant.url,
        "collections": collections,
    }


async def _check_redis(request: Request) -> dict:
    try:
        await request.app.state.redis.ping()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "url": request.app.state.settings.redis.url,
            "error": str(exc),
        }

    return {
        "status": "healthy",
        "url": request.app.state.settings.redis.url,
    }


@router.get("/health")
async def health(request: Request) -> dict:
    pg = await _check_postgres(request)
    qd = await _check_qdrant(request)
    rd = await _check_redis(request)

    all_healthy = (
        pg["status"] == "healthy"
        and qd["status"] == "healthy"
        and rd["status"] == "healthy"
    )

    return {
        "status": "ok" if all_healthy else "degraded",
        "services": {
            "postgres": pg,
            "qdrant": qd,
            "redis": rd,
        },
    }
