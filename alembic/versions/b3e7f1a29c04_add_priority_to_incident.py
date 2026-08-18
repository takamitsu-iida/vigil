"""add priority to incident

Revision ID: b3e7f1a29c04
Revises: 0dc5560430a6
Create Date: 2026-08-18 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3e7f1a29c04"
down_revision: Union[str, Sequence[str], None] = "0dc5560430a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incident",
        sa.Column(
            "priority",
            sa.Enum("P1", "P2", "P3", "P4", name="priority"),
            nullable=False,
            server_default="P3",
        ),
    )


def downgrade() -> None:
    op.drop_column("incident", "priority")
