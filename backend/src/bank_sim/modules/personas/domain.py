"""Персона заёмщика: вымышленный клиент банка в форматах мира и то, что о нём знают источники банка."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bank_sim.modules.sessions.domain import SessionProfile
from bank_sim.modules.sources.domain import SourceProfile
from shared.contracts.application import Applicant
from world.identifiers import CENTURY_DIGIT, YEARS_PER_CENTURY, pinfl_check_digit

CARD = r"^\d{16}$"
ACCOUNT = r"^\d{20}$"


def pinfl_matches(pinfl: str, born: date) -> bool:
    """ПИНФЛ мира: цифра века и пола, ДДММГГ рождения, код района, номер, контрольная цифра."""
    century = born.year // YEARS_PER_CENTURY
    first_digits = {digit for (cent, _), digit in CENTURY_DIGIT.items() if cent == century}
    return (
        pinfl[0] in first_digits
        and pinfl[1:7] == f"{born:%d%m}{born.year % YEARS_PER_CENTURY:02d}"
        and pinfl[-1] == pinfl_check_digit(pinfl[:-1])
    )


class PersonaProfile(BaseModel):
    """Профиль персоны: данные заявки, карта, обязательные шаги и ответы источников банка."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    applicant: Applicant
    account: str = Field(pattern=ACCOUNT)
    card_balance: int = Field(ge=0)
    known_recipients: list[Annotated[str, Field(pattern=CARD)]] = Field(default_factory=list)
    biometry: Literal["passed", "failed"] = "passed"
    phone_owner_match: bool = True
    sources: SourceProfile = SourceProfile()
    session: SessionProfile | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.session is not None and self.applicant.device_id is None:
            raise ValueError("Сессии приложения нужно устройство заявителя")
        return self


class PersonaSeed(BaseModel):
    """Запись сида персоны: витрина для выбора и профиль."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=64)
    birth_date: date
    summary: str = Field(min_length=1, max_length=512)
    profile: PersonaProfile

    @model_validator(mode="after")
    def _pinfl(self) -> Self:
        if not pinfl_matches(self.profile.applicant.pinfl, self.birth_date):
            raise ValueError(f"ПИНФЛ персоны {self.code} не в формате мира или не сходится с датой рождения")
        return self


def age(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
