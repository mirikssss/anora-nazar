"""Контракт единственной проводки: одна живая попытка на бизнес-операцию

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 06:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_operations_business_operation",
        "operations",
        ["realm_id", "application_id", "operation_type", "tranche"],
        unique=True,
        postgresql_where=sa.text("status in ('in_progress', 'waiting_node', 'executed')"),
    )


def downgrade() -> None:
    op.drop_index("uq_operations_business_operation", table_name="operations")
