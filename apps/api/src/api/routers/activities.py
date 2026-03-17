"""Activity feed endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Activity, User
from api.dependencies import get_current_user, get_db

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
async def list_activities(
    conversation_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List activity feed for the current user."""
    query = (
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if conversation_id:
        query = query.where(Activity.conversation_id == conversation_id)

    result = await db.execute(query)
    activities = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": str(a.entity_id) if a.entity_id else None,
            "conversation_id": str(a.conversation_id) if a.conversation_id else None,
            "summary": a.summary,
            "created_at": a.created_at.isoformat(),
        }
        for a in activities
    ]
