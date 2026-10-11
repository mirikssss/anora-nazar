"""Сценарии использования модуля и границы транзакций."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.realms import repository
from node.modules.realms.domain import RealmContext
from node.modules.realms.models import SANDBOX, WORLD
from shared.errors import ConfigurationError, NotFoundError, ValidationFailedError


def ensure_world(session: Session, now: datetime) -> UUID:
    existing = repository.world(session)
    if existing is not None:
        return existing.id
    world_id = uuid4()
    repository.insert_if_absent(session, world_id, WORLD, now)
    return world_id


def world_id(session: Session) -> UUID:
    realm = repository.world(session)
    if realm is None:
        raise ConfigurationError("Общий мир не создан: выполните сидирование узла")
    return realm.id


def create_sandbox(session: Session, realm_id: UUID, now: datetime) -> RealmContext:
    """Песочницу создаёт окружение банка со своим идентификатором — он общий для всех сервисов."""
    existing = repository.get(session, realm_id)
    if existing is not None and existing.kind != SANDBOX:
        raise ValidationFailedError("realm_not_sandbox", "Этот идентификатор занят общим миром")
    repository.insert_if_absent(session, realm_id, SANDBOX, now)
    return RealmContext(id=realm_id, is_sandbox=True, world_id=world_id(session))


def resolve(session: Session, realm_id: UUID, now: datetime) -> RealmContext:
    realm = repository.get(session, realm_id)
    if realm is None:
        raise NotFoundError("realm_not_found", "Песочница не найдена или удалена по сроку")
    if realm.kind == SANDBOX:
        repository.touch(session, realm_id, now)
        return RealmContext(id=realm.id, is_sandbox=True, world_id=world_id(session))
    return RealmContext(id=realm.id, is_sandbox=False, world_id=realm.id)


def delete_sandbox(session: Session, realm_id: UUID) -> None:
    if repository.delete_sandbox(session, realm_id) == 0:
        raise NotFoundError("realm_not_found", "Песочница не найдена")


def delete_inactive(session: Session, now: datetime, ttl: timedelta) -> list[UUID]:
    return repository.delete_inactive_sandboxes(session, now - ttl)


def existing(session: Session, ids: list[UUID]) -> set[UUID]:
    return repository.existing(session, ids)
