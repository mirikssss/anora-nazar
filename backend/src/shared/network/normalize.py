"""Нормализация идентификаторов перед OPRF — одна для всех кредиторов (network-contract-1, «Токены», п. 1).

Неверное значение — ошибка у кредитора: в сеть ничего не уходит. Значение в текст ошибки не попадает.
"""

import re

from shared.contracts.network import TokenKind
from shared.errors import ValidationFailedError

# Форматы — свойства самих идентификаторов (контракт сети), а не рабочие параметры.
PHONE_COUNTRY = "998"
PHONE_SUBSCRIBER_DIGITS = 9
DEVICE_MAX_LENGTH = 128

_PINFL = re.compile(r"[0-9]{14}")
_CARD = re.compile(r"[0-9]{16}")
_INN = re.compile(r"[0-9]{9}")
_PHONE = re.compile(rf"{PHONE_COUNTRY}[0-9]{{{PHONE_SUBSCRIBER_DIGITS}}}")
_PHONE_SEPARATORS = re.compile(r"[\s\-()]")
_CARD_SEPARATORS = re.compile(r"[\s\-]")

TITLES: dict[TokenKind, str] = {
    "pinfl": "ПИНФЛ",
    "phone": "телефон",
    "device": "устройство",
    "card": "карта",
    "supplier_inn": "ИНН поставщика",
}


def _invalid(kind: TokenKind) -> ValidationFailedError:
    return ValidationFailedError(
        "network_identifier_invalid", f"Неверный формат идентификатора «{TITLES[kind]}» для сети", {"kind": kind}
    )


def _phone(value: str) -> str | None:
    digits = _PHONE_SEPARATORS.sub("", value).removeprefix("+")
    if len(digits) == PHONE_SUBSCRIBER_DIGITS:
        digits = PHONE_COUNTRY + digits
    return _matching(_PHONE, digits)


def _device(value: str) -> str | None:
    device = value.strip().lower()
    return device if 0 < len(device) <= DEVICE_MAX_LENGTH else None


def _matching(pattern: re.Pattern[str], value: str) -> str | None:
    return value if pattern.fullmatch(value) else None


def normalize(kind: TokenKind, value: str) -> str:
    """Каноническая запись значения: ПИНФЛ — 14 цифр, телефон — 998 и 9 цифр, устройство — без пробелов по краям
    в нижнем регистре до 128 символов, карта — 16 цифр, ИНН поставщика — 9 цифр."""
    match kind:
        case "pinfl":
            result = _matching(_PINFL, value.strip())
        case "phone":
            result = _phone(value)
        case "device":
            result = _device(value)
        case "card":
            result = _matching(_CARD, _CARD_SEPARATORS.sub("", value))
        case "supplier_inn":
            result = _matching(_INN, value.strip())
    if result is None:
        raise _invalid(kind)
    return result
