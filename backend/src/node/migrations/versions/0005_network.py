"""И4: сеть кредиторов — кеш токенов OPRF, уведомления оператора, ответы сети на прошлые моменты

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "network_tokens",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("value_key", sa.String(length=64), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("kind", "value_key", name=op.f("pk_network_tokens")),
    )
    op.create_table(
        "network_notifications",
        sa.Column("notification_id", sa.String(length=128), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("kinds", JSONB, nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_network_notifications_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["realm_id"], ["realms.id"], name=op.f("fk_network_notifications_realm_id_realms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("notification_id", name=op.f("pk_network_notifications")),
    )
    op.create_index(op.f("ix_network_notifications_realm_id"), "network_notifications", ["realm_id"], unique=False)
    op.create_table(
        "network_observations",
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract", sa.String(length=32), nullable=False),
        sa.Column("observation", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_network_observations_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("application_id", "as_of", name=op.f("pk_network_observations")),
    )


def downgrade() -> None:
    op.drop_table("network_observations")
    op.drop_index(op.f("ix_network_notifications_realm_id"), table_name="network_notifications")
    op.drop_table("network_notifications")
    op.drop_table("network_tokens")
