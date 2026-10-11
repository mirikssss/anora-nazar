"""Чистая логика модуля: версии событий, их интервалы действия и токены."""

from dataclasses import dataclass
from datetime import datetime
from typing import get_args

from shared.contracts.network import ActivityEvent, ActivityKind, TokenRef
from shared.crypto.canonical_json import sha256_hex

TokenKey = tuple[str, int, str]  # (тип, версия ключа, токен)
FACT_KINDS: frozenset[str] = frozenset({"application", "issuance", "transfer"})
META_KINDS: frozenset[str] = frozenset(get_args(ActivityKind)) - FACT_KINDS


def token_key(ref: TokenRef) -> TokenKey:
    return ref.kind, ref.key_version, ref.token


def event_tokens(event: ActivityEvent) -> list[TokenKey]:
    """Токены версии: ПИНФЛ заявителя и остальные, без повторов."""
    refs = ([event.subject] if event.subject is not None else []) + list(event.tokens)
    return list(dict.fromkeys(token_key(r) for r in refs))


def content_hash(event: ActivityEvent) -> str:
    """Повтор с тем же содержимым — дубль, с другим — конфликт; событие при этом не меняется."""
    return sha256_hex(event.model_dump(mode="json"))


@dataclass(frozen=True)
class EventVersion:
    """Версия события, как её видят счётчики: действует с received_at до valid_until."""

    lender: str
    subject: str | None
    fact: str
    occurred_at: datetime
    received_at: datetime
    valid_until: datetime | None

    def visible_at(self, as_of: datetime) -> bool:
        return self.received_at <= as_of and (self.valid_until is None or self.valid_until > as_of)


def valid_until(superseded_at: datetime | None, retracted_at: datetime | None) -> datetime | None:
    ends = [moment for moment in (superseded_at, retracted_at) if moment is not None]
    return min(ends) if ends else None


@dataclass(frozen=True)
class Span:
    id: int
    received_at: datetime
    superseded_at: datetime | None


@dataclass(frozen=True)
class Placement:
    """Куда встаёт исправление: с какого момента действует, чью версию обрезает и до какого момента действует само."""

    received_at: datetime
    cuts: int
    superseded_at: datetime | None


def place_correction(spans: list[Span], received_at: datetime) -> Placement:
    """Исправление действует с момента получения, но не раньше исходного события; обрезает версию, действовавшую
    в этот момент, и наследует её конец — так и прогон истории не по порядку даёт верные интервалы."""
    ordered = sorted(spans, key=lambda s: (s.received_at, s.id))
    start = max(received_at, ordered[0].received_at)
    current = [s for s in ordered if s.received_at <= start][-1]
    return Placement(received_at=start, cuts=current.id, superseded_at=current.superseded_at)
