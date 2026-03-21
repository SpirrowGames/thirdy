import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class SpecReview(TimestampMixin, Base):
    __tablename__ = "spec_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    specification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("specifications.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="'pending'")
    scope: Mapped[str] = mapped_column(String(20), server_default="'full'")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issues: Mapped[list | None] = mapped_column(JSON, server_default="'[]'")
    suggestions: Mapped[list | None] = mapped_column(JSON, server_default="'[]'")
    questions: Mapped[list | None] = mapped_column(JSON, server_default="'[]'")
    # Snapshot of spec content at review time (for rollback)
    spec_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="spec_reviews")
    specification: Mapped["Specification"] = relationship(back_populates="spec_reviews")
