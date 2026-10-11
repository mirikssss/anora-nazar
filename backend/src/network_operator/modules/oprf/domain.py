"""Чистая логика модуля: ключи OPRF на тип и версию и их применение к ослеплённым элементам."""

from dataclasses import dataclass

from shared.contracts.network import TokenKind
from shared.network import oprf

KEY_INFO = "anora-nazar:{kind}:{version}"


def key_info(kind: TokenKind, version: int) -> bytes:
    return KEY_INFO.format(kind=kind, version=version).encode()


@dataclass(frozen=True)
class ActiveKey:
    version: int
    secret: bytes


class KeyRing:
    """Активный ключ каждого типа; ключ не покидает оператора и не попадает в журналы."""

    def __init__(self, seed: bytes, versions: dict[TokenKind, int]) -> None:
        self._keys = {
            kind: ActiveKey(version, oprf.derive_key_pair(seed, key_info(kind, version))[0])
            for kind, version in versions.items()
        }

    def version(self, kind: TokenKind) -> int:
        return self._keys[kind].version

    def evaluate(self, kind: TokenKind, elements: list[bytes]) -> list[bytes]:
        """BlindEvaluate каждого элемента; неверный элемент — OprfError на весь пакет."""
        secret = self._keys[kind].secret
        return [oprf.blind_evaluate(secret, element) for element in elements]
