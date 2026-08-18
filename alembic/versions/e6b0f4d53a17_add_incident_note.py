"""add incident note table

Revision ID: e6b0f4d53a17
Revises: d5a9e3c42f06
Create Date: 2026-08-18 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6b0f4d53a17"
down_revision: Union[str, Sequence[str], None] = "d5a9e3c42f06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidentnote",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("incident_id", sa.String(), nullable=False),
        sa.Column("author_user_id", sa.String(), nullable=True),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidentnote_incident_id", "incidentnote", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incidentnote_incident_id", table_name="incidentnote")
    op.drop_table("incidentnote")
