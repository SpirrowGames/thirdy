"""Add decision tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "decision_points",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("resolved_option_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_decision_points_conversation_id", "decision_points", ["conversation_id"])

    op.create_table(
        "decision_options",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("decision_point_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pros", sa.Text(), server_default="[]", nullable=False),
        sa.Column("cons", sa.Text(), server_default="[]", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["decision_point_id"], ["decision_points.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_decision_options_decision_point_id", "decision_options", ["decision_point_id"])

    # Add FK from decision_points.resolved_option_id to decision_options.id
    op.create_foreign_key(
        "fk_decision_points_resolved_option_id",
        "decision_points",
        "decision_options",
        ["resolved_option_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_decision_points_resolved_option_id", "decision_points", type_="foreignkey")
    op.drop_table("decision_options")
    op.drop_table("decision_points")
