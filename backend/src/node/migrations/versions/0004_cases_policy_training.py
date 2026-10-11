"""И3: дела, стоп-лист, версии политики со вторым подписантом, запуски обучения, отказ в выдаче

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _realm_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["realm_id"], ["realms.id"], name=op.f(f"fk_{table}_realm_id_realms"), ondelete="CASCADE"
    )


def upgrade() -> None:
    op.alter_column("holds", "required_check", type_=sa.String(length=64), existing_nullable=False)
    op.add_column("staff_users", sa.Column("branch_id", sa.String(length=32), nullable=True))
    op.drop_constraint(op.f("ck_applications_status"), "applications", type_="check")
    op.create_check_constraint(
        op.f("ck_applications_status"), "applications", "status in ('active', 'cancelled', 'refused')"
    )
    op.add_column("model_versions", sa.Column("realm_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_model_versions_realm_id_realms"), "model_versions", "realms", ["realm_id"], ["id"], ondelete="CASCADE"
    )
    op.create_table(
        "training_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("versions", JSONB, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("status in ('queued', 'running', 'done', 'failed')", name=op.f("ck_training_runs_status")),
        _realm_fk("training_runs"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_runs")),
    )
    op.create_index(op.f("ix_training_runs_realm_id"), "training_runs", ["realm_id"], unique=False)
    op.create_table(
        "cases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("queue", sa.String(length=16), nullable=False),
        sa.Column("zone", sa.Integer(), nullable=False),
        sa.Column("strategy", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assignee", sa.String(length=64), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("checklist", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('open', 'in_progress', 'escalated', 'closed')", name=op.f("ck_cases_status")),
        sa.CheckConstraint("strategy in ('application', 'identity', 'coordination')", name=op.f("ck_cases_strategy")),
        _realm_fk("cases"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
    )
    op.create_index(op.f("ix_cases_realm_id"), "cases", ["realm_id"], unique=False)
    op.create_index("ix_cases_realm_queue_status", "cases", ["realm_id", "queue", "status"], unique=False)
    op.create_table(
        "case_applications",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("summary", JSONB, nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("basis", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_case_applications_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_case_applications_case_id_cases"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("case_id", "application_id", name=op.f("pk_case_applications")),
    )
    op.create_index("ix_case_applications_application", "case_applications", ["application_id"], unique=False)
    op.create_table(
        "case_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("audit_seq", sa.BigInteger(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_case_events_case_id_cases"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_events")),
    )
    op.create_index(op.f("ix_case_events_case_id"), "case_events", ["case_id"], unique=False)
    op.create_table(
        "stop_list",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("attr_kind", sa.String(length=32), nullable=False),
        sa.Column("attr_key", sa.String(length=64), nullable=False),
        sa.Column("attr_display", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("stop_list"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stop_list")),
    )
    op.create_index("ix_stop_list_attr", "stop_list", ["attr_kind", "attr_key"], unique=False)
    op.create_table(
        "policy_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("base_version", sa.String(length=64), nullable=False),
        sa.Column("changes", JSONB, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposed_by", sa.String(length=64), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resulting_version", sa.String(length=64), nullable=True),
        _realm_fk("policy_proposals"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_proposals")),
    )
    op.create_index(op.f("ix_policy_proposals_realm_id"), "policy_proposals", ["realm_id"], unique=False)
    op.create_table(
        "policy_versions",
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("realm_id", sa.UUID(), nullable=False),
        sa.Column("base_version", sa.String(length=64), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _realm_fk("policy_versions"),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_policy_versions")),
    )
    op.create_index(op.f("ix_policy_versions_realm_id"), "policy_versions", ["realm_id"], unique=False)


def downgrade() -> None:
    for table in ("policy_versions", "policy_proposals", "stop_list", "case_events", "case_applications", "cases"):
        op.drop_table(table)
    op.drop_table("training_runs")
    op.drop_constraint(op.f("fk_model_versions_realm_id_realms"), "model_versions", type_="foreignkey")
    op.drop_column("model_versions", "realm_id")
    op.drop_constraint(op.f("ck_applications_status"), "applications", type_="check")
    op.create_check_constraint(op.f("ck_applications_status"), "applications", "status in ('active', 'cancelled')")
    op.drop_column("staff_users", "branch_id")
    op.alter_column("holds", "required_check", type_=sa.String(length=32), existing_nullable=False)
