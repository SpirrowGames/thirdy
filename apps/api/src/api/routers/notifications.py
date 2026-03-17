"""Notification endpoints — list, mark read, dismiss."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Notification, User
from api.dependencies import get_current_user, get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user."""
    query = (
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_dismissed == False,
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(Notification.is_read == False)
    result = await db.execute(query)
    notifications = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


@router.get("/count")
async def notification_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get unread notification count."""
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read == False,
            Notification.is_dismissed == False,
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    await db.commit()
    return {"id": str(notification.id), "is_read": True}


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_notification(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss (soft-delete) a notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_dismissed = True
    await db.commit()
