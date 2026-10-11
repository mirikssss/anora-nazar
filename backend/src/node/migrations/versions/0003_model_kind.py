"""Формат артефакта модели: LightGBM или логистическая регрессия

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_versions", sa.Column("kind", sa.String(length=16), nullable=False, server_default="lightgbm"))
    op.alter_column("model_versions", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("model_versions", "kind")
