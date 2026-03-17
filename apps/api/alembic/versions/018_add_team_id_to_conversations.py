"""Add team_id to conversations

Revision ID: 018
Revises: 017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("team_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_conversations_team_id", "conversations", ["team_id"])
    op.create_foreign_key("fk_conversations_team_id", "conversations", "teams", ["team_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_conversations_team_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_team_id", "conversations")
    op.drop_column("conversations", "team_id")
