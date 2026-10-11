"""Сценарии использования модуля и границы транзакций."""

import os
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.identity import repository
from node.modules.identity.domain import (
    Principal,
    StaffPrincipal,
    SystemPrincipal,
    hash_api_key,
    issue_staff_token,
    read_staff_token,
)
from node.modules.identity.models import StaffRole, StaffUser
from shared.config import load_yaml
from shared.errors import ConfigurationError, ForbiddenError, NotFoundError, UnauthorizedError


def seed(session: Session, seeds_dir: Path) -> None:
    """Роли и сотрудники — из YAML; ключи систем банка — из окружения, в базе только их хеши."""
    for role in load_yaml(seeds_dir / "roles.yaml")["roles"]:
        repository.upsert_role(
            session,
            {
                "code": role["code"],
                "title": role["title"],
                "home_path": role["home_path"],
                "summary": role["summary"],
                "permissions": role["permissions"],
                "restrictions": role.get("restrictions", []),
            },
        )
    for user in load_yaml(seeds_dir / "staff_users.yaml")["staff_users"]:
        repository.upsert_user(
            session,
            {
                "code": user["code"],
                "role_code": user["role"],
                "display_name": user["display_name"],
                "division": user["division"],
                "branch_id": user.get("branch_id"),
            },
        )
    for client in load_yaml(seeds_dir / "api_clients.yaml")["api_clients"]:
        key = os.environ.get(client["key_env"])
        if not key:
            raise ConfigurationError(f"Не задан ключ системы банка: {client['key_env']}")
        repository.upsert_client(
            session,
            {
                "name": client["name"],
                "key_hash": hash_api_key(key),
                "scopes": client["scopes"],
            },
        )


def _staff_principal(user: StaffUser, role: StaffRole, realm_id: UUID) -> StaffPrincipal:
    return StaffPrincipal(
        user_code=user.code,
        role_code=role.code,
        display_name=user.display_name,
        division=user.division,
        permissions=frozenset(role.permissions),
        realm_id=realm_id,
        branch_id=user.branch_id,
    )


def authenticate(session: Session, bearer: str, secret: str) -> Principal:
    staff = read_staff_token(bearer, secret)
    if staff is not None:
        user_code, realm_id = staff
        found = repository.user_with_role(session, user_code)
        if found is None:
            raise UnauthorizedError("unknown_user", "Сотрудник не найден")
        return _staff_principal(found[0], found[1], realm_id)
    client = repository.client_by_key_hash(session, hash_api_key(bearer))
    if client is None:
        raise UnauthorizedError("invalid_credentials", "Неверный ключ или токен")
    return SystemPrincipal(client=client.name, scopes=frozenset(client.scopes))


def demo_login(session: Session, user_code: str, realm_id: UUID, secret: str) -> tuple[str, StaffPrincipal]:
    found = repository.user_with_role(session, user_code)
    if found is None:
        raise NotFoundError("unknown_user", "Такого сотрудника нет")
    return issue_staff_token(user_code, realm_id, secret), _staff_principal(found[0], found[1], realm_id)


def list_roles(session: Session) -> list[tuple[StaffRole, list[StaffUser]]]:
    return repository.roles_with_users(session)


def require_staff_permission(session: Session, user_code: str, permission: str) -> None:
    """Для команд стенда: сотрудник существует и имеет право — как при входе через API."""
    found = repository.user_with_role(session, user_code)
    if found is None or permission not in found[1].permissions:
        raise ForbiddenError("permission_required", f"У сотрудника {user_code} нет права «{permission}»")
