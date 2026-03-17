"""Add conversation branching fields

Revision ID: 019
Revises: 018
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("parent_id", UUID(as_uuid=True), nullable=True))
    op.add_column("conversations", sa.Column("branch_point_message_id", UUID(as_uuid=True), nullable=True))
    op.add_column("conversations", sa.Column("branch_status", sa.String(20), nullable=True))
    op.create_index("ix_conversations_parent_id", "conversations", ["parent_id"])
    op.create_foreign_key("fk_conversations_parent_id", "conversations", "conversations", ["parent_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_conversations_branch_point_msg", "conversations", "messages", ["branch_point_message_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_conversations_branch_point_msg", "conversations", type_="foreignkey")
    op.drop_constraint("fk_conversations_parent_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_parent_id", "conversations")
    op.drop_column("conversations", "branch_status")
    op.drop_column("conversations", "branch_point_message_id")
    op.drop_column("conversations", "parent_id")
