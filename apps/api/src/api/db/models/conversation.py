import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default="gen_random_uuid()"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    specifications: Mapped[list["Specification"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    decision_points: Mapped[list["DecisionPoint"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    designs: Mapped[list["Design"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    generated_tasks: Mapped[list["GeneratedTask"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    generated_codes: Mapped[list["GeneratedCode"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    voice_transcripts: Mapped[list["VoiceTranscript"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    github_issues: Mapped[list["GitHubIssue"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
