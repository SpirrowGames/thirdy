"""Add spec_reviews table

Revision ID: 020
Revises: 019
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spec_reviews",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("specification_id", UUID(as_uuid=True), sa.ForeignKey("specifications.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", sa.String(255), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="full"),
        sa.Column("summary", JSON(), nullable=True),
        sa.Column("issues", JSON(), nullable=True, server_default="[]"),
        sa.Column("suggestions", JSON(), nullable=True, server_default="[]"),
        sa.Column("questions", JSON(), nullable=True, server_default="[]"),
        sa.Column("spec_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("spec_reviews")
