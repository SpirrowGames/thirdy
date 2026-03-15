from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared_schemas import HealthResponse

from api.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    db_connected = False
    try:
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        pass

    redis_connected = False
    try:
        redis_pool = request.app.state.redis_pool
        if await redis_pool.ping():
            redis_connected = True
    except Exception:
        pass

    return HealthResponse(
        status="ok", db_connected=db_connected, redis_connected=redis_connected
    )
