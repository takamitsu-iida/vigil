"""add acknowledged_by_user_id to incident

Revision ID: g8d2f6e75c39
Revises: f7c1e5d64b28
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g8d2f6e75c39"
down_revision: Union[str, Sequence[str], None] = "f7c1e5d64b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incident",
        sa.Column("acknowledged_by_user_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incident", "acknowledged_by_user_id")
