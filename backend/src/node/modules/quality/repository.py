"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from node.modules.quality.models import QualityReport


def add(session: Session, report: QualityReport) -> None:
    session.add(report)


def latest(session: Session, realm_ids: Iterable[UUID]) -> QualityReport | None:
    return session.scalars(
        select(QualityReport)
        .where(QualityReport.realm_id.in_(list(realm_ids)))
        .order_by(QualityReport.created_at.desc())
        .limit(1)
    ).one_or_none()
