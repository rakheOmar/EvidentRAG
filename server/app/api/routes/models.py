from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
async def models(request: Request) -> dict[str, object]:
    context_manager = request.app.state.context_manager
    return {
        "generation_model": context_manager.model_name,
        "context_window": context_manager.context_window,
    }
