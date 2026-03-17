"""Utility for recording activity log entries."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Activity

logger = logging.getLogger(__name__)


async def log_activity(
    db: AsyncSession,
    user_id: UUID,
    action: str,
    conversation_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    summary: str | None = None,
) -> None:
    """Record an activity log entry.

    Args:
        db: Database session.
        user_id: User who performed the action.
        action: Action identifier (e.g., "spec_approved", "pr_created").
        conversation_id: Related conversation.
        entity_type: Type of entity affected.
        entity_id: ID of entity affected.
        summary: Human-readable summary.
    """
    activity = Activity(
        user_id=user_id,
        conversation_id=conversation_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
    )
    db.add(activity)
    # Don't commit — caller manages the transaction
