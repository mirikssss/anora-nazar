"""Песочницы: создание вместе с контуром узла, сброс, удаление брошенных; контур у оператора сети удаляется
вместе с песочницей."""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.sandboxes import repository
from bank_sim.modules.sandboxes.models import Sandbox
from bank_sim.network_gateway import NetworkGateway
from shared.errors import AppError, ConfigurationError, NotFoundError

log = logging.getLogger(__name__)


def add(session: Session, sandbox_id: UUID, now: datetime) -> None:
    repository.add(session, Sandbox(id=sandbox_id, created_at=now, last_seen_at=now))


def touch(session: Session, sandbox_id: UUID, now: datetime) -> None:
    if not repository.exists(session, sandbox_id):
        raise NotFoundError("sandbox_not_found", "Песочница не найдена или удалена по сроку — начните заново")
    repository.touch(session, sandbox_id, now)


def remove(session: Session, sandbox_id: UUID) -> None:
    repository.remove(session, sandbox_id)


def inactive(session: Session, now: datetime, ttl: timedelta) -> list[UUID]:
    return repository.seen_before(session, now - ttl)


def all_ids(session: Session) -> list[UUID]:
    return repository.all_ids(session)


def forget_in_network(network: NetworkGateway | None, realm_id: UUID) -> None:
    """События, результаты и подписки песочницы у оператора сети. Сбой оператора сброс не останавливает: контур
    песочницы — случайный идентификатор, его данные никому больше не видны."""
    if network is None:
        return
    try:
        network.delete_realm(realm_id)
    except (AppError, ConfigurationError) as exc:
        log.warning("контур песочницы %s у оператора сети не удалён: %s", realm_id, exc)
