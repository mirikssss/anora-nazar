"""Контуры песочниц: сброс удаляет все данные песочницы у оператора; демо-сбой выключает сеть одному контуру."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.activity import service as activity
from network_operator.modules.confirmed import service as confirmed
from network_operator.modules.quotas import service as quotas
from network_operator.modules.realms import repository
from network_operator.modules.watches import service as watches
from shared.errors import UpstreamUnavailableError


def delete(session: Session, realm_id: UUID) -> None:
    activity.delete_realm(session, realm_id)
    confirmed.delete_realm(session, realm_id)
    watches.delete_realm(session, realm_id)
    quotas.delete_realm(session, realm_id)
    repository.end_outage(session, realm_id)


def set_outage(session: Session, realm_id: UUID, active: bool, now: datetime) -> None:
    if active:
        repository.start_outage(session, realm_id, now)
    else:
        repository.end_outage(session, realm_id)


def ensure_available(session: Session, realm_id: UUID | None) -> None:
    if realm_id is not None and repository.in_outage(session, realm_id):
        raise UpstreamUnavailableError(
            "network_unavailable", "Сеть кредиторов недоступна (сбой стенда для этой песочницы)"
        )


def outages(session: Session) -> list[UUID]:
    return repository.outages(session)
