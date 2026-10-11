"""OPRF по RFC 9497: режим OPRF (0x00), набор ristretto255-SHA512, примитивы libsodium через pysodium.

Кредитор ослепляет значение (Blind) и снимает ослепление (Finalize), оператор применяет ключ (BlindEvaluate).
Значения оператор не видит, ключа нет ни у одного кредитора. Проверено тестовыми векторами RFC 9497, приложение A.1.1.
"""

import hashlib
from dataclasses import dataclass

import pysodium

from shared.contracts.network import TokenKind

MODE_OPRF = 0x00
SUITE_ID = b"ristretto255-SHA512"
CONTEXT_STRING = b"OPRFV1-" + bytes([MODE_OPRF]) + b"-" + SUITE_ID
HASH_TO_GROUP_DST = b"HashToGroup-" + CONTEXT_STRING
HASH_TO_SCALAR_DST = b"HashToScalar-" + CONTEXT_STRING
DERIVE_KEY_PAIR_DST = b"DeriveKeyPair" + CONTEXT_STRING
FINALIZE_LABEL = b"Finalize"

ELEMENT_BYTES = 32  # Ne
SCALAR_BYTES = 32  # Ns
UNIFORM_BYTES = 64  # вход hash_to_ristretto255 и HashToScalar
TOKEN_BYTES = 32  # токен — первые 32 байта выхода Finalize (network-contract-1)
SHA512_BLOCK_BYTES = 128  # s_in_bytes для expand_message_xmd
SHA512_BYTES = 64  # b_in_bytes
MAX_DST_BYTES = 255
MAX_EXPAND_BLOCKS = 255
MAX_COUNTER = 255
INPUT_SEPARATOR = b"\x00"


class OprfError(ValueError):
    """Неверный элемент группы или вход, который отображается в нейтральный элемент."""


@dataclass(frozen=True)
class Blinded:
    blind: bytes
    element: bytes


def _i2osp(value: int, length: int) -> bytes:
    return value.to_bytes(length, "big")


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def expand_message_xmd(msg: bytes, dst: bytes, length: int) -> bytes:
    """expand_message_xmd на SHA-512 (RFC 9380, п. 5.3.1)."""
    blocks = -(-length // SHA512_BYTES)
    if len(dst) > MAX_DST_BYTES or blocks > MAX_EXPAND_BLOCKS:
        raise OprfError("expand_message_xmd: слишком длинный DST или выход")
    dst_prime = dst + _i2osp(len(dst), 1)
    b0 = _sha512(bytes(SHA512_BLOCK_BYTES) + msg + _i2osp(length, 2) + _i2osp(0, 1) + dst_prime)
    previous = _sha512(b0 + _i2osp(1, 1) + dst_prime)
    output = previous
    for i in range(2, blocks + 1):
        previous = _sha512(bytes(a ^ b for a, b in zip(b0, previous, strict=True)) + _i2osp(i, 1) + dst_prime)
        output += previous
    return output[:length]


def hash_to_group(msg: bytes) -> bytes:
    """hash_to_ristretto255 (RFC 9380): 64 равномерных байта → одностороннее отображение ristretto255."""
    point: bytes = pysodium.crypto_core_ristretto255_from_hash(
        expand_message_xmd(msg, HASH_TO_GROUP_DST, UNIFORM_BYTES)
    )
    return point


def hash_to_scalar(msg: bytes, dst: bytes = HASH_TO_SCALAR_DST) -> bytes:
    """64 равномерных байта как little-endian число по модулю порядка группы."""
    scalar: bytes = pysodium.crypto_core_ristretto255_scalar_reduce(expand_message_xmd(msg, dst, UNIFORM_BYTES))
    return scalar


def _scalar_mult(scalar: bytes, element: bytes) -> bytes:
    try:
        product: bytes = pysodium.crypto_scalarmult_ristretto255(scalar, element)
    except ValueError as exc:  # libsodium отказывает на нейтральном элементе в результате
        raise OprfError("Произведение — нейтральный элемент группы") from exc
    return product


def derive_key_pair(seed: bytes, info: bytes) -> tuple[bytes, bytes]:
    """DeriveKeyPair (RFC 9497, п. 3.2.1): закрытый скаляр и публичный элемент из seed и info."""
    derive_input = seed + _i2osp(len(info), 2) + info
    for counter in range(MAX_COUNTER + 1):
        secret = hash_to_scalar(derive_input + _i2osp(counter, 1), DERIVE_KEY_PAIR_DST)
        if secret != bytes(SCALAR_BYTES):
            public: bytes = pysodium.crypto_scalarmult_ristretto255_base(secret)
            return secret, public
    raise OprfError("DeriveKeyPair: не удалось получить ненулевой скаляр")


def oprf_input(kind: TokenKind, normalized: str) -> bytes:
    """Вход OPRF: тип ‖ 0x00 ‖ нормализованное значение — одно значение разных типов даёт разные токены."""
    return kind.encode() + INPUT_SEPARATOR + normalized.encode()


def blind(value: bytes, blind_scalar: bytes | None = None) -> Blinded:
    """Blind: случайный скаляр (или заданный — для тестовых векторов) на элемент входа."""
    scalar: bytes = pysodium.crypto_core_ristretto255_scalar_random() if blind_scalar is None else blind_scalar
    element = hash_to_group(value)
    if element == bytes(ELEMENT_BYTES):
        raise OprfError("Вход отображается в нейтральный элемент")
    return Blinded(blind=scalar, element=_scalar_mult(scalar, element))


def validate_element(element: bytes) -> None:
    """DeserializeElement: корректная кодировка ristretto255 и не нейтральный элемент."""
    if (
        len(element) != ELEMENT_BYTES
        or element == bytes(ELEMENT_BYTES)
        or not pysodium.crypto_core_ristretto255_is_valid_point(element)
    ):
        raise OprfError("Не элемент группы ristretto255")


def blind_evaluate(secret: bytes, element: bytes) -> bytes:
    """BlindEvaluate на стороне оператора: ключ на ослеплённый элемент."""
    validate_element(element)
    return _scalar_mult(secret, element)


def finalize(value: bytes, blind_scalar: bytes, evaluated: bytes) -> bytes:
    """Finalize: снять ослепление и захешировать вместе со входом."""
    validate_element(evaluated)
    inverse: bytes = pysodium.crypto_core_ristretto255_scalar_invert(blind_scalar)
    unblinded = _scalar_mult(inverse, evaluated)
    return _sha512(_i2osp(len(value), 2) + value + _i2osp(len(unblinded), 2) + unblinded + FINALIZE_LABEL)


def token_of(output: bytes) -> str:
    return output[:TOKEN_BYTES].hex()
