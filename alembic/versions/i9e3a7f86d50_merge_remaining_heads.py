"""merge remaining migration heads

Revision ID: i9e3a7f86d50
Revises: b0c1d2e3f4a5, g8d2f6e75c39
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = "i9e3a7f86d50"
down_revision: Union[str, Sequence[str], None] = ("b0c1d2e3f4a5", "g8d2f6e75c39")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass