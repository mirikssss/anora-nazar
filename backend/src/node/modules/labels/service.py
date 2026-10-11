"""Метки из фактов источников и выборка известных к дате меток для обучения."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.labels import repository
from node.modules.labels.domain import from_fact
from node.modules.labels.models import Label


def record_from_fact(
    session: Session,
    realm_id: UUID,
    fact_type: str,
    payload: dict[str, Any],
    event_id: UUID,
    occurred_at: datetime,
    received_at: datetime,
) -> int:
    """Метка ставится только на заявки своего контура, известные узлу; остальные идентификаторы пропускаются."""
    draft = from_fact(fact_type, payload)
    if draft is None:
        return 0
    rows = []
    for external_id in draft.application_external_ids:
        app_id = applications.find_id(session, realm_id, external_id)
        if app_id is None:
            continue
        rows.append(
            {
                "realm_id": realm_id,
                "application_id": app_id,
                "typology": draft.typology,
                "kind": draft.kind,
                "source": draft.source,
                "confirmation": draft.confirmation,
                "case_key": draft.case_key,
                "trainable": True,
                "event_id": event_id,
                "occurred_at": occurred_at,
                "received_at": received_at,
            }
        )
    repository.add_many(session, rows)
    return len(rows)


def known_as_of(
    session: Session, realm_ids: tuple[UUID, ...], application_ids: list[UUID], cutoff: datetime
) -> list[Label]:
    return repository.known_as_of(session, realm_ids, application_ids, cutoff)


def latest_received(session: Session, realm_ids: tuple[UUID, ...]) -> datetime | None:
    return repository.latest_received(session, realm_ids)


def record_case_outcome(
    session: Session,
    realm_id: UUID,
    application_ids: list[UUID],
    *,
    typology: str | None,
    kind: str,
    source: str,
    case_key: str,
    event_id: UUID,
    now: datetime,
) -> int:
    """Метка по исходу дела: только из исходов, которые её разрешают (Блок 4); источник — кто вёл дело."""
    repository.add_many(
        session,
        [
            {
                "realm_id": realm_id,
                "application_id": app_id,
                "typology": typology,
                "kind": kind,
                "source": source,
                "confirmation": "confirmed",
                "case_key": case_key,
                "trainable": True,
                "event_id": event_id,
                "occurred_at": now,
                "received_at": now,
            }
            for app_id in application_ids
        ],
    )
    return len(application_ids)


def issued_application_ids(session: Session, realm_ids: tuple[UUID, ...]) -> set[UUID]:
    """Заявки с исходом кредита (созрел) — значит, выданы: для ретро-поиска по истории мира."""
    return repository.applications_with_kind(session, realm_ids, "weak_negative")
