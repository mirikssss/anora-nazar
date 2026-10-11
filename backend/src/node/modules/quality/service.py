"""Отчёты качества: запись после обучения и последний видимый контуру отчёт."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.quality import repository
from node.modules.quality.models import QualityReport
from node.modules.realms.domain import RealmContext
from shared.errors import NotFoundError


def save(session: Session, realm_id: UUID, report: dict[str, Any], now: datetime) -> QualityReport:
    row = QualityReport(id=uuid4(), realm_id=realm_id, created_at=now, report=report)
    repository.add(session, row)
    return row


def latest(session: Session, realm: RealmContext) -> QualityReport:
    found = repository.latest(session, realm.visible_ids)
    if found is None:
        raise NotFoundError("quality_report_not_found", "Модели ещё не обучались: отчёта качества нет")
    return found
