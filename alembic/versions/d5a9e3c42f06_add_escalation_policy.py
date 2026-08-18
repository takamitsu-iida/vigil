"""add escalation policy and multi-step fields

Revision ID: d5a9e3c42f06
Revises: c4f8d2b31e05
Create Date: 2026-08-18 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5a9e3c42f06"
down_revision: Union[str, Sequence[str], None] = "c4f8d2b31e05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "escalationpolicy",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("team_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalationpolicy_team_name", "escalationpolicy", ["team_name"])

    op.create_table(
        "escalationstep",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("timeout_minutes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["escalationpolicy.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("incident", sa.Column("policy_id", sa.String(), nullable=True))
    op.add_column("incident", sa.Column("escalation_step", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key(None, "incident", "escalationpolicy", ["policy_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(None, "incident", type_="foreignkey")
    op.drop_column("incident", "escalation_step")
    op.drop_column("incident", "policy_id")
    op.drop_table("escalationstep")
    op.drop_index("ix_escalationpolicy_team_name", table_name="escalationpolicy")
    op.drop_table("escalationpolicy")
