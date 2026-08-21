"""merge add_source and remove_email_slack branches

Revision ID: b0c1d2e3f4a5
Revises: 1a2b3c4d5e6f, a1b2c3d4e5f6
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = ("1a2b3c4d5e6f", "a1b2c3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
