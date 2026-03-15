import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class PullRequest(TimestampMixin, Base):
    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generated_codes.id", ondelete="CASCADE"), index=True
    )
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    branch_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="'creating'")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="pull_requests")
    code: Mapped["GeneratedCode"] = relationship(back_populates="pull_requests")
