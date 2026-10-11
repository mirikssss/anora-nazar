"""Чистая логика модуля: кто вызывает оператора и с какими правами."""

import hashlib
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scope = Literal["oprf", "activity", "query", "confirmed", "history", "realms", "demo"]
LENDER_SCOPES: frozenset[str] = frozenset({"oprf", "activity", "query", "confirmed", "history"})


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@dataclass(frozen=True)
class Caller:
    client: str
    lender: str | None
    scopes: frozenset[str]

    @property
    def history(self) -> bool:
        """Прогон синтетической истории: received_at и as_of из запроса, квота OPRF не действует."""
        return "history" in self.scopes


@dataclass(frozen=True)
class Callback:
    """Куда оператор доставляет уведомления кредитора о новых совпадениях."""

    url: str
    key: str


class _Seed(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CallbackSeed(_Seed):
    url_env: str
    key_env: str


class LenderSeed(_Seed):
    code: str = Field(min_length=1, max_length=16)
    callback: CallbackSeed | None = None


class ClientSeed(_Seed):
    name: str = Field(min_length=1, max_length=64)
    lender: str | None
    scopes: list[Scope] = Field(min_length=1)
    key_env: str


class ClientsSeed(_Seed):
    lenders: list[LenderSeed]
    api_clients: list[ClientSeed]

    @model_validator(mode="after")
    def _lenders_known(self) -> Self:
        codes = {lender.code for lender in self.lenders}
        for client in self.api_clients:
            needs_lender = bool(LENDER_SCOPES & set(client.scopes))
            if needs_lender != (client.lender is not None) or (client.lender and client.lender not in codes):
                raise ValueError(f"Клиент {client.name}: права кредитора — только у известного кредитора")
        return self
