"""add webhook urls to user

Revision ID: f7c1e5d64b28
Revises: e6b0f4d53a17
Create Date: 2026-08-18 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7c1e5d64b28"
down_revision: Union[str, Sequence[str], None] = "e6b0f4d53a17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("slack_webhook_url", sa.String(), nullable=False, server_default=""))
    op.add_column("user", sa.Column("discord_webhook_url", sa.String(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("user", "discord_webhook_url")
    op.drop_column("user", "slack_webhook_url")
