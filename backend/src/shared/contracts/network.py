"""Контракт сети кредиторов (network-contract-1): кредитор ↔ оператор сети. Описание — network_operator/SPEC.md.

В сеть уходят только токены OPRF (псевдонимизированные данные) и счётчики. Значений идентификаторов оператор
не видит, ключа OPRF нет ни у одного кредитора.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "network-contract-1"
MAX_BATCH = 500

TokenKind = Literal["pinfl", "phone", "device", "card", "supplier_inn"]
TOKEN_KINDS: tuple[TokenKind, ...] = ("pinfl", "phone", "device", "card", "supplier_inn")
ActivityKind = Literal["application", "issuance", "transfer", "correction", "retraction"]
Channel = Literal["online", "program"]
Confirmation = Literal["confirmed_fraud", "confirmed_coercion"]

TOKEN_PATTERN = r"^[0-9a-f]{64}$"
POINT_PATTERN = r"^[0-9a-f]{64}$"

# Счётчики ответа: имя фиксирует окно, смена окна — новая версия контракта.
CounterName = Literal[
    "pinfl_lenders_1h",
    "pinfl_lenders_7d",
    "phone_people_24h",
    "phone_people_30d",
    "device_people_30d",
    "card_borrowers_30d",
    "card_lenders_30d",
    "supplier_borrowers_30d",
    "supplier_lenders_30d",
]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TokenRef(_Strict):
    kind: TokenKind
    key_version: int = Field(ge=1)
    token: str = Field(pattern=TOKEN_PATTERN)


class EvaluationIn(_Strict):
    """Ослеплённые элементы ristretto255 одного типа идентификатора."""

    kind: TokenKind
    blinded: list[Annotated[str, Field(pattern=POINT_PATTERN)]] = Field(min_length=1, max_length=MAX_BATCH)


class EvaluationOut(_Strict):
    kind: TokenKind
    key_version: int
    evaluated: list[str]


class ActivityEvent(_Strict):
    """Событие активности кредитора. event_id уникален у кредитора; повтор с тем же содержимым — не дубль.

    correction заменяет токены события refers_to, retraction убирает его из счётчиков (ошибочная запись);
    обе действуют с момента получения оператором. Отказ или отмена заявки клиентом — не retraction:
    заявка была подана, и для серии по ПИНФЛ это важно.
    """

    event_id: str = Field(min_length=1, max_length=128)
    kind: ActivityKind
    occurred_at: datetime
    received_at: datetime | None = Field(
        default=None, description="Только для прогона истории (право history); иначе время получения оператором"
    )
    channel: Channel | None = None
    subject: TokenRef | None = Field(default=None, description="Токен ПИНФЛ заявителя")
    tokens: list[TokenRef] = Field(default_factory=list, max_length=16)
    credit_share: float | None = Field(default=None, ge=0, le=1, description="Доля кредита в переводе")
    refers_to: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _shape(self) -> "ActivityEvent":
        meta = self.kind in ("correction", "retraction")
        if meta != (self.refers_to is not None):
            raise ValueError("refers_to — только у correction и retraction")
        if self.kind in ("application", "issuance", "transfer", "correction") and self.subject is None:
            raise ValueError("Нужен токен ПИНФЛ заявителя")
        if self.subject is not None and self.subject.kind != "pinfl":
            raise ValueError("subject — токен ПИНФЛ")
        if self.kind == "transfer" and (self.credit_share is None or not any(t.kind == "card" for t in self.tokens)):
            raise ValueError("У перевода нужны токен карты-получателя и доля кредита")
        return self


class ActivityIn(_Strict):
    events: list[ActivityEvent] = Field(min_length=1, max_length=MAX_BATCH)


class ActivityOut(_Strict):
    accepted: int
    duplicates: int
    conflicts: list[str] = Field(description="event_id, пришедшие повторно с другим содержимым")
    unknown_references: list[str] = Field(description="event_id correction/retraction без исходного события")


class CounterQuery(_Strict):
    """ref — непрозрачная ссылка кредитора на заявку: по ней придёт уведомление о новом совпадении."""

    ref: str = Field(min_length=1, max_length=128)
    subject: TokenRef
    tokens: list[TokenRef] = Field(default_factory=list, max_length=16)
    as_of: datetime | None = Field(default=None, description="Только с правом history: счётчики на прошлый момент")
    watch_until: datetime | None = Field(default=None, description="До какого момента сообщать о новых совпадениях")


class CountersIn(_Strict):
    queries: list[CounterQuery] = Field(min_length=1, max_length=MAX_BATCH)


class ConfirmedMatch(_Strict):
    kind: TokenKind
    typology: str
    confirmation: Confirmation


class CounterResult(_Strict):
    ref: str
    as_of: datetime
    counters: dict[CounterName, int]
    confirmed: list[ConfirmedMatch]


class CountersOut(_Strict):
    contract: str = CONTRACT_VERSION
    results: list[CounterResult]


class ConfirmedResult(_Strict):
    """Результат закрытого дела. Только идентификаторы мошенника; идентификаторы жертвы в сеть не уходят."""

    result_id: str = Field(min_length=1, max_length=128)
    typology: str = Field(min_length=1, max_length=8)
    confirmation: Confirmation
    tokens: list[TokenRef] = Field(min_length=1, max_length=16)
    confirmed_at: datetime


class ConfirmedIn(_Strict):
    results: list[ConfirmedResult] = Field(min_length=1, max_length=MAX_BATCH)


class MatchNotification(_Strict):
    """Оператор → кредитор: у заявки ref появилось новое совпадение у другого кредитора."""

    notification_id: str
    ref: str
    kinds: list[TokenKind]
    occurred_at: datetime


class OutageIn(_Strict):
    active: bool
