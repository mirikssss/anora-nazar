"""И3: платформа программ и акты приёмки, приложение заёмщика, карты и переводы, жалобы, запуски сценариев

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _realm_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["realm_id"], ["sandboxes.id"], name=op.f(f"fk_{table}_realm_id_sandboxes"), ondelete="CASCADE"
    )


def upgrade() -> None:
    op.create_table(
        "program_helpers",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("district", sa.String(length=128), nullable=False),
        sa.Column("mahalla", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_program_helpers")),
    )
    op.create_index(op.f("ix_program_helpers_district"), "program_helpers", ["district"], unique=False)
    op.create_table(
        "program_suppliers",
        sa.Column("inn", sa.String(length=9), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("district", sa.String(length=128), nullable=False),
        sa.Column("registered_on", sa.Date(), nullable=False),
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("inn", name=op.f("pk_program_suppliers")),
    )
    op.create_index(op.f("ix_program_suppliers_district"), "program_suppliers", ["district"], unique=False)
    op.create_table(
        "acceptance_acts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.String(length=32), nullable=False),
        sa.Column("signer_id", sa.String(length=64), nullable=False),
        sa.Column("signer_role", sa.String(length=32), nullable=False),
        sa.Column("signed_on", sa.Date(), nullable=False),
        sa.Column("invoice_amount", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("acceptance_acts"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acceptance_acts")),
    )
    op.create_index(
        "ix_acceptance_acts_realm_application", "acceptance_acts", ["realm_id", "application_id"], unique=False
    )
    op.add_column("operations", sa.Column("acceptance_act_id", sa.String(length=32), nullable=True))

    op.create_table(
        "borrower_personas",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_borrower_personas")),
    )
    op.create_table(
        "borrower_applications",
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.String(length=32), nullable=False),
        sa.Column("persona_code", sa.String(length=32), nullable=True),
        sa.Column("intent_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("intent_answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pressure_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("borrower_applications"),
        sa.PrimaryKeyConstraint("realm_id", "application_id", name=op.f("pk_borrower_applications")),
    )

    op.create_table(
        "card_accounts",
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("pinfl", sa.String(length=14), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("card_accounts"),
        sa.PrimaryKeyConstraint("realm_id", "account", name=op.f("pk_card_accounts")),
    )
    op.create_table(
        "card_credits",
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.String(length=32), nullable=False),
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("pinfl", sa.String(length=14), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_before", sa.BigInteger(), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("card_credits"),
        sa.PrimaryKeyConstraint("realm_id", "application_id", name=op.f("pk_card_credits")),
    )
    op.create_table(
        "card_recipients",
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("pinfl", sa.String(length=14), nullable=False),
        sa.Column("card", sa.String(length=16), nullable=False),
        sa.Column("first_used_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("card_recipients"),
        sa.PrimaryKeyConstraint("realm_id", "pinfl", "card", name=op.f("pk_card_recipients")),
    )
    op.create_table(
        "transfers",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.String(length=32), nullable=False),
        sa.Column("pinfl", sa.String(length=14), nullable=False),
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("recipient_card", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("recipient_is_new", sa.Boolean(), nullable=False),
        sa.Column("balance_before_credit", sa.BigInteger(), nullable=False),
        sa.Column("credit_share", sa.Float(), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=16), nullable=False),
        sa.Column("recommendation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("node_error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("own_rule", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("transfers"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfers")),
    )
    op.create_index("ix_transfers_realm_application", "transfers", ["realm_id", "application_id"], unique=False)

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("typology", sa.String(length=8), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("application_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("case_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("incidents"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(op.f("ix_incidents_realm_id"), "incidents", ["realm_id"], unique=False)

    op.create_table(
        "scenario_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("scenario_code", sa.String(length=64), nullable=False),
        sa.Column("applications", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _realm_fk("scenario_runs"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_runs")),
        sa.UniqueConstraint("realm_id", "number", name="uq_scenario_runs_realm_number"),
    )


def downgrade() -> None:
    op.drop_table("scenario_runs")
    op.drop_index(op.f("ix_incidents_realm_id"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_transfers_realm_application", table_name="transfers")
    op.drop_table("transfers")
    op.drop_table("card_recipients")
    op.drop_table("card_credits")
    op.drop_table("card_accounts")
    op.drop_table("borrower_applications")
    op.drop_table("borrower_personas")
    op.drop_column("operations", "acceptance_act_id")
    op.drop_index("ix_acceptance_acts_realm_application", table_name="acceptance_acts")
    op.drop_table("acceptance_acts")
    op.drop_index(op.f("ix_program_suppliers_district"), table_name="program_suppliers")
    op.drop_table("program_suppliers")
    op.drop_index(op.f("ix_program_helpers_district"), table_name="program_helpers")
    op.drop_table("program_helpers")
