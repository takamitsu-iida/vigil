"""add fingerprint to incident

Revision ID: c4f8d2b31e05
Revises: b3e7f1a29c04
Create Date: 2026-08-18 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8d2b31e05"
down_revision: Union[str, Sequence[str], None] = "b3e7f1a29c04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incident", sa.Column("fingerprint", sa.String(), nullable=True))
    op.create_index("ix_incident_fingerprint", "incident", ["fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_incident_fingerprint", table_name="incident")
    op.drop_column("incident", "fingerprint")
