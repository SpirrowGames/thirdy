import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class GeneratedTask(TimestampMixin, Base):
    __tablename__ = "generated_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    design_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("designs.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), server_default="'medium'")
    status: Mapped[str] = mapped_column(String(20), server_default="'pending'")
    dependencies: Mapped[str] = mapped_column(Text, server_default="'[]'")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")

    conversation: Mapped["Conversation"] = relationship(back_populates="generated_tasks")
    design: Mapped["Design"] = relationship(back_populates="generated_tasks")
    generated_codes: Mapped[list["GeneratedCode"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
