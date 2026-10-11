"""Кредиторы и системы стенда: сиды ключей, проверка ключа, адреса уведомлений."""

import os
from pathlib import Path

from sqlalchemy.orm import Session

from network_operator.modules.clients import repository
from network_operator.modules.clients.domain import Callback, Caller, ClientsSeed, hash_api_key
from shared.config import load_yaml
from shared.errors import ConfigurationError, ForbiddenError, UnauthorizedError

SEED_FILE = "api_clients.yaml"


def _seed_file(seeds_dir: Path) -> ClientsSeed:
    return ClientsSeed.model_validate(load_yaml(seeds_dir / SEED_FILE))


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(f"Не задана переменная окружения {name}")
    return value


def seed(session: Session, seeds_dir: Path) -> None:
    """Права — из YAML, ключи — из окружения; в базе только хеши ключей."""
    for client in _seed_file(seeds_dir).api_clients:
        repository.upsert(
            session,
            {
                "name": client.name,
                "lender": client.lender,
                "key_hash": hash_api_key(_env(client.key_env)),
                "scopes": list(client.scopes),
            },
        )


def callbacks(seeds_dir: Path) -> dict[str, Callback]:
    """Адреса и ключи уведомлений кредиторов — из окружения при старте; секреты в базу не попадают."""
    return {
        lender.code: Callback(url=_env(lender.callback.url_env).rstrip("/"), key=_env(lender.callback.key_env))
        for lender in _seed_file(seeds_dir).lenders
        if lender.callback is not None
    }


def authenticate(session: Session, bearer: str) -> Caller:
    client = repository.by_key_hash(session, hash_api_key(bearer))
    if client is None:
        raise UnauthorizedError("invalid_credentials", "Неверный ключ кредитора")
    return Caller(client=client.name, lender=client.lender, scopes=frozenset(client.scopes))


def require(caller: Caller, scope: str) -> None:
    if scope not in caller.scopes:
        raise ForbiddenError("scope_required", f"Нет права «{scope}»", {"scope": scope})


def lenders(session: Session) -> list[str]:
    return repository.lenders(session)
