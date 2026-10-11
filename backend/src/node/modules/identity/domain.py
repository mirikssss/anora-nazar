"""Чистая логика модуля без ввода-вывода: принципалы и подписанный токен демо-входа."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from uuid import UUID

STAFF_TOKEN_PREFIX = "st."


@dataclass(frozen=True)
class SystemPrincipal:
    """Система банка с API-ключом."""

    client: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class StaffPrincipal:
    """Сотрудник узла, вошедший в демо выбором роли внутри своей песочницы."""

    user_code: str
    role_code: str
    display_name: str
    division: str
    permissions: frozenset[str]
    realm_id: UUID
    branch_id: str | None = None


Principal = SystemPrincipal | StaffPrincipal


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_staff_token(user_code: str, realm_id: UUID, secret: str) -> str:
    payload = _b64(json.dumps({"u": user_code, "r": str(realm_id)}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{STAFF_TOKEN_PREFIX}{payload}.{signature}"


def read_staff_token(token: str, secret: str) -> tuple[str, UUID] | None:
    """Возвращает (код сотрудника, песочница) или None, если токен подделан или испорчен."""
    if not token.startswith(STAFF_TOKEN_PREFIX):
        return None
    try:
        payload, signature = token[len(STAFF_TOKEN_PREFIX) :].split(".", 1)
        expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_unb64(payload))
        return str(data["u"]), UUID(data["r"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
