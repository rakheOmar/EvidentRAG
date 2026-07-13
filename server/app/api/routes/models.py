from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(prefix="/api/v1/model-context", tags=["model-context"])


@router.get("")
async def get_model_context(request: Request) -> dict[str, object]:
    context_manager = request.app.state.context_manager
    if context_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Model context is unavailable"},
        )
    return {
        "generation_model": context_manager.model_name,
        "context_window": context_manager.context_window,
    }
