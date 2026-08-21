"""remove email and slack_user_id from user

Revision ID: a1b2c3d4e5f6
Revises: f7c1e5d64b28
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f7c1e5d64b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("user", "email")
    op.drop_column("user", "slack_user_id")


def downgrade() -> None:
    op.add_column("user", sa.Column("slack_user_id", sa.String(), nullable=False, server_default=""))
    op.add_column("user", sa.Column("email", sa.String(), nullable=False, server_default=""))
