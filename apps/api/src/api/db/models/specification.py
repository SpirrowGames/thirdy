import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class Specification(TimestampMixin, Base):
    __tablename__ = "specifications"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="'draft'")

    conversation: Mapped["Conversation"] = relationship(back_populates="specifications")
    designs: Mapped[list["Design"]] = relationship(
        back_populates="specification", cascade="all, delete-orphan"
    )
    spec_reviews: Mapped[list["SpecReview"]] = relationship(
        back_populates="specification", cascade="all, delete-orphan"
    )
