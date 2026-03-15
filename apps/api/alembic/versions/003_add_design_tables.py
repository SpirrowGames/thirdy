"""Add design tables

Revision ID: 003
Revises: 002
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "designs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["specification_id"], ["specifications.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_designs_conversation_id", "designs", ["conversation_id"])
    op.create_index("ix_designs_specification_id", "designs", ["specification_id"])

    # Add design_id FK to decision_points
    op.add_column(
        "decision_points",
        sa.Column("design_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_decision_points_design_id",
        "decision_points",
        "designs",
        ["design_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_decision_points_design_id", "decision_points", ["design_id"])


def downgrade() -> None:
    op.drop_index("ix_decision_points_design_id", "decision_points")
    op.drop_constraint("fk_decision_points_design_id", "decision_points", type_="foreignkey")
    op.drop_column("decision_points", "design_id")
    op.drop_table("designs")
