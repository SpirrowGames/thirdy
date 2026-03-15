"""Add vote tables

Revision ID: 007
Revises: 006
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vote_sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("decision_point_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("share_token", sa.String(64), nullable=False),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["decision_point_id"], ["decision_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_vote_sessions_decision_point_id", "vote_sessions", ["decision_point_id"])
    op.create_index("ix_vote_sessions_share_token", "vote_sessions", ["share_token"], unique=True)

    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("vote_session_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=False),
        sa.Column("voter_name", sa.String(255), nullable=False),
        sa.Column("voter_token", sa.String(64), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vote_session_id"], ["vote_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["option_id"], ["decision_options.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("vote_session_id", "voter_token", name="uq_vote_session_voter"),
    )
    op.create_index("ix_votes_vote_session_id", "votes", ["vote_session_id"])
    op.create_index("ix_votes_option_id", "votes", ["option_id"])


def downgrade() -> None:
    op.drop_table("votes")
    op.drop_table("vote_sessions")
