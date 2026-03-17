"""Notification model for in-app notifications."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

from api.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # watch_alert, vote_reminder, audit_complete, etc.
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)  # e.g., /chat/{conversation_id}
    is_read = Column(Boolean, default=False, nullable=False)
    is_dismissed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
