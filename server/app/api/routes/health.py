from __future__ import annotations

import asyncio

from sqlalchemy import text

from fastapi import APIRouter, Request

router = APIRouter()


async def _check_postgres(request: Request) -> dict:
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return {"status": "unhealthy"}

    return {"status": "healthy"}


async def _check_qdrant(request: Request) -> dict:
    try:
        await request.app.state.qdrant_store.health_check()
    except Exception:
        return {"status": "unhealthy"}

    return {"status": "healthy"}


async def _check_redis(request: Request) -> dict:
    try:
        await request.app.state.redis.ping()
    except Exception:
        return {"status": "unhealthy"}

    return {"status": "healthy"}


@router.get("/health")
async def health(request: Request) -> dict:
    pg, qd, rd = await asyncio.gather(
        _check_postgres(request),
        _check_qdrant(request),
        _check_redis(request),
    )

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
