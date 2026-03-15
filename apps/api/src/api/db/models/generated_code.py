import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class GeneratedCode(TimestampMixin, Base):
    __tablename__ = "generated_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generated_tasks.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="'draft'")

    conversation: Mapped["Conversation"] = relationship(back_populates="generated_codes")
    task: Mapped["GeneratedTask"] = relationship(back_populates="generated_codes")
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        back_populates="code", cascade="all, delete-orphan"
    )
