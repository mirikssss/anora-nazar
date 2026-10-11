"""Форматы идентификаторов мира: ПИНФЛ, телефон, устройство, счёт, ИНН, карта. Все значения уникальны в мире."""

from datetime import date
from random import Random

from world.sampling import pick

# Форматы — свойства самих идентификаторов, а не параметры генератора.
CENTURY_DIGIT = {(19, True): "3", (19, False): "4", (20, True): "5", (20, False): "6"}
PINFL_CHECK_WEIGHTS = (7, 3, 1)  # контрольная цифра — как в машиночитаемой зоне паспорта, по модулю 10
PINFL_SERIAL_SPACE = 1000
DISTRICT_CODE_SPACE = 1000
PHONE_COUNTRY = "998"
PHONE_SUBSCRIBER_SPACE = 10_000_000
ACCOUNT_SPACE = 10**20  # счёт в банке Узбекистана — 20 цифр
LEGAL_INN_FIRST_DIGITS = ("2", "3")  # ИНН юрлица — 9 цифр, начинается с 2 или 3
LEGAL_INN_TAIL_SPACE = 10**8
DEVICE_ID_BITS = 64
YEARS_PER_CENTURY = 100
CARD_LENGTH = 16  # номер карты — 16 цифр, последняя — контрольная по алгоритму Луна


def pinfl_check_digit(body: str) -> str:
    total = sum(int(digit) * PINFL_CHECK_WEIGHTS[i % len(PINFL_CHECK_WEIGHTS)] for i, digit in enumerate(body))
    return str(total % 10)


def luhn_check_digit(body: str) -> str:
    """Контрольная цифра Луна: каждая вторая цифра справа, начиная с последней цифры тела, удваивается."""
    total = 0
    for index, digit in enumerate(reversed(body)):
        value = int(digit) * (2 if index % 2 == 0 else 1)
        total += value - 9 if value > 9 else value
    return str(-total % 10)


class Identifiers:
    """Выдаёт уникальные идентификаторы; повтор случайного значения перетягивается."""

    def __init__(self, rng: Random, phone_operator_codes: list[str]) -> None:
        self._rng = rng
        self._operators = phone_operator_codes
        self._issued: dict[str, None] = {}

    def _unique(self, candidate: str) -> bool:
        if candidate in self._issued:
            return False
        self._issued[candidate] = None
        return True

    def pinfl(self, born: date, male: bool, district_code: int) -> str:
        digit = CENTURY_DIGIT.get((born.year // YEARS_PER_CENTURY, male))
        if digit is None:
            raise ValueError(f"Год рождения {born.year} вне форматов ПИНФЛ")
        prefix = f"{digit}{born:%d%m}{born.year % YEARS_PER_CENTURY:02d}{district_code % DISTRICT_CODE_SPACE:03d}"
        while True:
            body = f"{prefix}{self._rng.randrange(PINFL_SERIAL_SPACE):03d}"
            candidate = body + pinfl_check_digit(body)
            if self._unique(candidate):
                return candidate

    def phone(self) -> str:
        while True:
            operator = pick(self._rng, self._operators)
            candidate = f"{PHONE_COUNTRY}{operator}{self._rng.randrange(PHONE_SUBSCRIBER_SPACE):07d}"
            if self._unique(candidate):
                return candidate

    def device(self) -> str:
        while True:
            candidate = f"dev-{self._rng.getrandbits(DEVICE_ID_BITS):016x}"
            if self._unique(candidate):
                return candidate

    def account(self) -> str:
        while True:
            candidate = f"{self._rng.randrange(ACCOUNT_SPACE):020d}"
            if self._unique(candidate):
                return candidate

    def card(self, prefixes: list[str]) -> str:
        """Номер карты: префикс платёжной системы, случайные цифры и контрольная цифра Луна."""
        while True:
            prefix = pick(self._rng, prefixes)
            digits = CARD_LENGTH - len(prefix) - 1
            body = f"{prefix}{self._rng.randrange(10**digits):0{digits}d}"
            candidate = body + luhn_check_digit(body)
            if self._unique(candidate):
                return candidate

    def legal_inn(self) -> str:
        while True:
            candidate = pick(self._rng, LEGAL_INN_FIRST_DIGITS) + f"{self._rng.randrange(LEGAL_INN_TAIL_SPACE):08d}"
            if self._unique(candidate):
                return candidate
