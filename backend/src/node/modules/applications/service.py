"""Сценарии использования модуля и границы транзакций."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.applications import repository
from node.modules.applications.domain import VersionOutcome, classify_version
from node.modules.applications.models import ACTIVE, CANCELLED, REFUSED, Application
from shared.contracts.application import ApplicationSnapshot
from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConflictError, NotFoundError


@dataclass(frozen=True)
class VersionResult:
    outcome: VersionOutcome
    application: Application


def ensure(session: Session, realm_id: UUID, external_id: str, channel: str, subject_key: str, now: datetime) -> UUID:
    """Находит заявку или создаёт пустую строку: версия 0, ещё ни одного снимка."""
    found = repository.find_id(session, realm_id, external_id)
    if found is not None:
        return found
    created = repository.insert_new(
        session,
        {
            "id": uuid4(),
            "realm_id": realm_id,
            "external_id": external_id,
            "channel": channel,
            "subject_key": subject_key,
            "status": ACTIVE,
            "current_version": 0,
            "assessed_version": None,
            "latest_decision_id": None,
            "assessment_point": None,
            "assessment_outcome": None,
            "assessment_level": None,
            "assessment_valid_until": None,
            "needs_reassessment": False,
            "reassessment_cause": None,
            "version_gap_since": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    if created is not None:
        return created
    raced = repository.find_id(session, realm_id, external_id)
    if raced is None:
        raise ConflictError("application_race", "Заявка создаётся параллельным запросом, повторите")
    return raced


def find_id(session: Session, realm_id: UUID, external_id: str) -> UUID | None:
    return repository.find_id(session, realm_id, external_id)


def lock(session: Session, ids: set[UUID]) -> dict[UUID, Application]:
    return repository.lock_many(session, ids)


def apply_snapshot(
    session: Session,
    app: Application,
    number: int,
    snapshot: ApplicationSnapshot,
    occurred_at: datetime,
    received_at: datetime,
    *,
    authoritative: bool,
) -> VersionResult:
    """Применяет снимок к заблокированной заявке.

    authoritative=True — полный снимок от владельца (оценка или ответ на запрос снимка): версия из будущего
    принимается, пропущенные версии больше не нужны. Иначе действует строгий порядок событий.
    """
    current = app.current_version or None
    outcome = classify_version(current, number)
    data = snapshot.model_dump(mode="json")
    digest = sha256_hex(data)
    if outcome is VersionOutcome.SAME:
        stored = repository.version(session, app.id, number)
        if stored is not None and stored.snapshot_hash != digest:
            raise ConflictError("version_conflict", f"Версия {number} уже получена с другим содержимым")
        return VersionResult(outcome, app)
    if outcome is VersionOutcome.GAP and not authoritative:
        if app.version_gap_since is None:
            app.version_gap_since = received_at
        return VersionResult(outcome, app)
    if outcome is VersionOutcome.STALE:
        return VersionResult(outcome, app)
    repository.insert_version(
        session,
        {
            "application_id": app.id,
            "version": number,
            "snapshot": data,
            "snapshot_hash": digest,
            "occurred_at": occurred_at,
            "received_at": received_at,
        },
    )
    app.current_version = number
    app.version_gap_since = None
    app.updated_at = received_at
    return VersionResult(VersionOutcome.APPLIED, app)


def snapshot_of(session: Session, app: Application, number: int) -> tuple[ApplicationSnapshot, str]:
    stored = repository.version(session, app.id, number)
    if stored is None:
        raise NotFoundError("version_not_found", f"Нет версии {number} заявки")
    return ApplicationSnapshot.model_validate(stored.snapshot), stored.snapshot_hash


def mark_for_reassessment(
    session: Session, realm_id: UUID, ids: set[UUID], cause: dict[str, Any], now: datetime
) -> list[UUID]:
    """Пометка «нужна новая оценка». Строки уже заблокированы вызывающим по возрастанию id."""
    if not ids:
        return []
    return repository.mark(session, realm_id, sorted(ids), cause, now)


@dataclass(frozen=True)
class AssessmentSummary:
    decision_id: UUID
    version: int
    point: str
    outcome: str
    level: str | None
    valid_until: datetime


def record_assessment(app: Application, summary: AssessmentSummary, now: datetime) -> None:
    app.assessed_version = summary.version
    app.latest_decision_id = summary.decision_id
    app.assessment_point = summary.point
    app.assessment_outcome = summary.outcome
    app.assessment_level = summary.level
    app.assessment_valid_until = summary.valid_until
    app.needs_reassessment = False
    app.reassessment_cause = None
    app.updated_at = now


def cancel(app: Application, now: datetime) -> None:
    app.status = CANCELLED
    app.updated_at = now


def refuse(app: Application, now: datetime) -> None:
    """Отказ в этой выдаче по итогу проверки; новая заявка оценивается заново."""
    app.status = REFUSED
    app.updated_at = now


def open_ids_of_subject(session: Session, realm_id: UUID, subject_key: str, now: datetime) -> list[UUID]:
    """Кого из заявок человека касается новый факт: оценка с истёкшим сроком и так будет пересчитана."""
    return repository.open_ids_of_subject(session, realm_id, subject_key, now)


def open_ids(session: Session, realm_id: UUID, ids: set[UUID], now: datetime) -> set[UUID]:
    return repository.open_ids(session, realm_id, ids, now)


def get_visible(session: Session, realm_ids: tuple[UUID, ...], external_id: str) -> Application:
    app = repository.by_external(session, realm_ids, external_id)
    if app is None:
        raise NotFoundError("application_not_found", "Заявка не найдена")
    return app


def gaps_older_than(session: Session, before: datetime) -> list[Application]:
    return repository.gaps_older_than(session, before)


def get_by_id(session: Session, application_id: UUID) -> Application:
    app = session.get(Application, application_id)
    if app is None:
        raise NotFoundError("application_not_found", "Заявка не найдена")
    return app
