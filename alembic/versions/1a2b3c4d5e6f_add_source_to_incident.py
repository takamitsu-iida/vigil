"""add source to incident

Revision ID: 1a2b3c4d5e6f
Revises: f7c1e5d64b28
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f7c1e5d64b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incident", sa.Column("source", sa.String(), nullable=False, server_default=""))
    op.create_index("ix_incident_source", "incident", ["source"])


def downgrade() -> None:
    op.drop_index("ix_incident_source", table_name="incident")
    op.drop_column("incident", "source")
