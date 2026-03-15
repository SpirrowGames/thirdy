"""Add pull request tables

Revision ID: 006
Revises: 005
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("code_id", sa.Uuid(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("pr_url", sa.String(500), nullable=True),
        sa.Column("branch_name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="creating", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["code_id"], ["generated_codes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_pull_requests_conversation_id", "pull_requests", ["conversation_id"])
    op.create_index("ix_pull_requests_code_id", "pull_requests", ["code_id"])


def downgrade() -> None:
    op.drop_table("pull_requests")
