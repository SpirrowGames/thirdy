"""Add github_repo to conversations

Revision ID: 017
Revises: 016
"""

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("github_repo", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "github_repo")
