"""Снимок заявки — контракт конвейера и узла: конвейер его собирает, узел хранит неизменяемым."""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PINFL = re.compile(r"^\d{14}$")
UZ_PHONE = re.compile(r"^998\d{9}$")
INN = re.compile(r"^\d{9}$")


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Applicant(_Strict):
    pinfl: str
    phone: str
    device_id: str | None = Field(default=None, min_length=1, max_length=128)
    address: str | None = Field(default=None, min_length=1, max_length=512)
    employer_inn: str | None = None

    @field_validator("pinfl")
    @classmethod
    def _pinfl(cls, value: str) -> str:
        if not PINFL.fullmatch(value):
            raise ValueError("ПИНФЛ — 14 цифр")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        digits = _digits(value)
        if not UZ_PHONE.fullmatch(digits):
            raise ValueError("Телефон — номер Узбекистана: 998 и 9 цифр")
        return digits

    @field_validator("employer_inn")
    @classmethod
    def _inn(cls, value: str | None) -> str | None:
        if value is not None and not INN.fullmatch(value):
            raise ValueError("ИНН работодателя — 9 цифр")
        return value


class Loan(_Strict):
    amount: int = Field(gt=0)
    term_months: int = Field(gt=0, le=600)
    purpose: str | None = Field(default=None, max_length=256)


class MandatoryChecks(_Strict):
    """Итоги обязательных шагов № 3759, которые конвейер выполнил до вызова узла."""

    self_ban: Literal["active", "none"]
    bureau: Literal["free", "blocked", "busy"]
    biometry: Literal["passed", "failed"]
    phone_owner_match: bool


class ProgramDetails(_Strict):
    helper_id: str = Field(min_length=1, max_length=64)
    supplier_inn: str
    supplier_account: str = Field(min_length=1, max_length=64)
    item_code: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=32)
    unit_price: int = Field(gt=0)
    quantity: int = Field(gt=0)
    district: str = Field(min_length=1, max_length=128)

    @field_validator("supplier_inn")
    @classmethod
    def _inn(cls, value: str) -> str:
        if not INN.fullmatch(value):
            raise ValueError("ИНН поставщика — 9 цифр")
        return value

    @property
    def contract_amount(self) -> int:
        return self.unit_price * self.quantity


class ApplicationSnapshot(_Strict):
    channel: Literal["online", "program"]
    branch_id: str = Field(min_length=1, max_length=64)
    employee_id: str | None = Field(default=None, min_length=1, max_length=64)
    applicant: Applicant
    loan: Loan
    disbursement_account: str | None = Field(default=None, min_length=1, max_length=64)
    program: ProgramDetails | None = None
    mandatory_checks: MandatoryChecks
    session_refs: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _channel_parts(self) -> Self:
        if self.channel == "online" and self.disbursement_account is None:
            raise ValueError("Онлайн-заявке нужен счёт зачисления")
        if self.channel == "program" and self.program is None:
            raise ValueError("Программной заявке нужны поставщик, товар и цена")
        if self.channel == "online" and self.program is not None:
            raise ValueError("У онлайн-заявки нет программной части")
        return self
