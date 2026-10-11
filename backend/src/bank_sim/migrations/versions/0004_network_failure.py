"""И4: кнопка сбоя «сеть недоступна»

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "failure_flags", sa.Column("network_unavailable", sa.Boolean(), server_default=sa.false(), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("failure_flags", "network_unavailable")
