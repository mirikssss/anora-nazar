"""И2: версии и выпуски моделей, метки, программные договоры, отчёты качества

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 06:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _realm_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["realm_id"], ["realms.id"], name=op.f(f"fk_{table}_realm_id_realms"), ondelete="CASCADE"
    )


def _application_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["application_id"],
        ["applications.id"],
        name=op.f(f"fk_{table}_application_id_applications"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    # В И1 реестр был пуст: таблица пересоздаётся с артефактом, калибровкой и метриками.
    op.drop_table("model_versions")
    op.create_table(
        "model_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("typology", sa.String(length=8), nullable=False),
        sa.Column("points", JSONB, nullable=False),
        sa.Column("feature_set_version", sa.String(length=32), nullable=False),
        sa.Column("feature_names", JSONB, nullable=False),
        sa.Column("artifact", sa.Text(), nullable=False),
        sa.Column("calibration", JSONB, nullable=False),
        sa.Column("training", JSONB, nullable=False),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
    )
    op.create_table(
        "model_releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("model_version_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_model_releases_model_version_id_model_versions"),
            ondelete="CASCADE",
        ),
        _realm_fk("model_releases"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_releases")),
    )
    op.create_index(
        "ix_model_releases_realm_name", "model_releases", ["realm_id", "model_name", "approved_at"], unique=False
    )
    op.create_table(
        "labels",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("typology", sa.String(length=8), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confirmation", sa.String(length=16), nullable=False),
        sa.Column("case_key", sa.String(length=128), nullable=True),
        sa.Column("trainable", sa.Boolean(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind in ('positive', 'strong_negative', 'weak_negative')", name=op.f("ck_labels_kind")),
        _application_fk("labels"),
        _realm_fk("labels"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_labels")),
    )
    op.create_index("ix_labels_application", "labels", ["application_id"], unique=False)
    op.create_index("ix_labels_realm_received", "labels", ["realm_id", "received_at"], unique=False)
    op.create_table(
        "program_contracts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("application_version", sa.Integer(), nullable=False),
        sa.Column("branch_key", sa.String(length=64), nullable=False),
        sa.Column("employee_key", sa.String(length=64), nullable=True),
        sa.Column("helper_key", sa.String(length=64), nullable=False),
        sa.Column("supplier_key", sa.String(length=64), nullable=False),
        sa.Column("item_code", sa.String(length=64), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("district", sa.String(length=128), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        _application_fk("program_contracts"),
        _realm_fk("program_contracts"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_program_contracts")),
    )
    op.create_index(
        "ix_program_contracts_item", "program_contracts", ["item_code", "unit", "received_at"], unique=False
    )
    op.create_index("ix_program_contracts_branch", "program_contracts", ["branch_key", "received_at"], unique=False)
    op.create_index("ix_program_contracts_helper", "program_contracts", ["helper_key", "received_at"], unique=False)
    op.create_index("ix_program_contracts_received", "program_contracts", ["realm_id", "received_at"], unique=False)
    op.create_table(
        "quality_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report", JSONB, nullable=False),
        _realm_fk("quality_reports"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_reports")),
    )
    # Признаки на as_of ищут факты по человеку и по сущности с сортировкой по времени получения.
    op.create_index(
        "ix_source_facts_type_subject", "source_facts", ["type", "subject_key", "received_at"], unique=False
    )
    op.create_index("ix_source_facts_type_entity", "source_facts", ["type", "entity_id", "received_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_source_facts_type_entity", table_name="source_facts")
    op.drop_index("ix_source_facts_type_subject", table_name="source_facts")
    op.drop_table("quality_reports")
    for index in ("item", "branch", "helper", "received"):
        op.drop_index(f"ix_program_contracts_{index}", table_name="program_contracts")
    op.drop_table("program_contracts")
    op.drop_index("ix_labels_realm_received", table_name="labels")
    op.drop_index("ix_labels_application", table_name="labels")
    op.drop_table("labels")
    op.drop_index("ix_model_releases_realm_name", table_name="model_releases")
    op.drop_table("model_releases")
    op.drop_table("model_versions")
    op.create_table(
        "model_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("typology", sa.String(length=8), nullable=False),
        sa.Column("points", JSONB, nullable=False),
        sa.Column("feature_set_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('shadow', 'active', 'retired')", name=op.f("ck_model_versions_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
    )
