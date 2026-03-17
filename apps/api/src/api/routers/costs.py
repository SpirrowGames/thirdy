"""Cost tracking proxy — forwards requests to Lexora's /stats/costs API."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from api.config import settings
from api.db.models import User
from api.dependencies import get_current_user

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("")
async def get_costs(
    period: str = Query("today", description="today, month, all, or YYYY-MM-DD"),
    model: str | None = Query(None),
    _current_user: User = Depends(get_current_user),
):
    """Get aggregated API costs from Lexora."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {"period": period}
            if model:
                params["model"] = model
            resp = await client.get(
                f"{settings.lexora_base_url}/stats/costs",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Lexora unavailable: {e}") from e


@router.get("/recent")
async def get_recent_costs(
    limit: int = Query(50, ge=1, le=200),
    _current_user: User = Depends(get_current_user),
):
    """Get recent request cost records from Lexora."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.lexora_base_url}/stats/costs/recent",
                params={"limit": limit},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Lexora unavailable: {e}") from e
