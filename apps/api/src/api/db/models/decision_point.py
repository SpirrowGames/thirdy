import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class DecisionPoint(TimestampMixin, Base):
    __tablename__ = "decision_points"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="'pending'")
    resolved_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_options.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="decision_points")
    options: Mapped[list["DecisionOption"]] = relationship(
        back_populates="decision_point",
        cascade="all, delete-orphan",
        foreign_keys="DecisionOption.decision_point_id",
    )


class DecisionOption(TimestampMixin, Base):
    __tablename__ = "decision_options"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    decision_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_points.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pros: Mapped[str] = mapped_column(Text, server_default="'[]'")
    cons: Mapped[str] = mapped_column(Text, server_default="'[]'")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    decision_point: Mapped["DecisionPoint"] = relationship(
        back_populates="options",
        foreign_keys=[decision_point_id],
    )
