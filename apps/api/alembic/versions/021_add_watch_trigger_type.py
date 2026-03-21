"""Add trigger_type to watch_reports

Revision ID: 021
Revises: 020
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "watch_reports",
        sa.Column("trigger_type", sa.String(20), server_default="manual", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("watch_reports", "trigger_type")
