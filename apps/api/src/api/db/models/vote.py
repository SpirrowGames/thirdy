import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from api.db.base import Base, TimestampMixin


class VoteSession(TimestampMixin, Base):
    __tablename__ = "vote_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    decision_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_points.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), server_default="'open'")
    share_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    decision_point: Mapped["DecisionPoint"] = relationship(
        back_populates="vote_sessions",
    )
    votes: Mapped[list["Vote"]] = relationship(
        back_populates="vote_session",
        cascade="all, delete-orphan",
    )


class Vote(TimestampMixin, Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("vote_session_id", "voter_token", name="uq_vote_session_voter"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    vote_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vote_sessions.id", ondelete="CASCADE"), index=True
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_options.id", ondelete="CASCADE"), index=True
    )
    voter_name: Mapped[str] = mapped_column(String(255))
    voter_token: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    vote_session: Mapped["VoteSession"] = relationship(back_populates="votes")
