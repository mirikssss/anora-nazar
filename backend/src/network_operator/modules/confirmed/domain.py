"""Чистая логика модуля: результат проверки другого кредитора, как его видят счётчики."""

from dataclasses import dataclass
from datetime import datetime

from shared.contracts.network import ConfirmedResult
from shared.crypto.canonical_json import sha256_hex


@dataclass(frozen=True)
class ConfirmedFact:
    lender: str
    kind: str
    typology: str
    confirmation: str
    confirmed_at: datetime
    received_at: datetime

    def visible_at(self, as_of: datetime) -> bool:
        return self.confirmed_at <= as_of and self.received_at <= as_of


def content_hash(result: ConfirmedResult) -> str:
    return sha256_hex(result.model_dump(mode="json"))
