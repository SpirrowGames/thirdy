import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class WatchReport(TimestampMixin, Base):
    __tablename__ = "watch_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[list | None] = mapped_column(JSON, server_default="[]")
    watch_targets: Mapped[list | None] = mapped_column(JSON, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), server_default="completed")
    trigger_type: Mapped[str] = mapped_column(String(20), server_default="'manual'")

    conversation: Mapped["Conversation"] = relationship(back_populates="watch_reports")
