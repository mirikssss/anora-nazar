"""Клиентская часть сети: OPRF по тестовым векторам RFC 9497 и нормализация идентификаторов."""

import pytest

from shared.errors import ValidationFailedError
from shared.network import oprf
from shared.network.normalize import normalize

# RFC 9497, приложение A.1.1: ristretto255-SHA512, режим OPRF.
SEED = bytes.fromhex("a3" * 32)
KEY_INFO = bytes.fromhex("74657374206b6579")
SK = "5ebcea5ee37023ccb9fc2d2019f9d7737be85591ae8652ffa9ef0f4d37063b0e"
BLIND = "64d37aed22a27f5191de1c1d69fadb899d8862b58eb4220029e036ec4c1f6706"
VECTORS = [
    (
        "00",
        "609a0ae68c15a3cf6903766461307e5c8bb2f95e7e6550e1ffa2dc99e412803c",
        "7ec6578ae5120958eb2db1745758ff379e77cb64fe77b0b2d8cc917ea0869c7e",
        "527759c3d9366f277d8c6020418d96bb393ba2afb20ff90df23fb7708264e2f3"
        "ab9135e3bd69955851de4b1f9fe8a0973396719b7912ba9ee8aa7d0b5e24bcf6",
    ),
    (
        "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
        "da27ef466870f5f15296299850aa088629945a17d1f5b7f5ff043f76b3c06418",
        "b4cbf5a4f1eeda5a63ce7b77c7d23f461db3fcab0dd28e4e17cecb5c90d02c25",
        "f4a74c9c592497375e796aa837e907b1a045d34306a749db9f34221f7e750cb4"
        "f2a6413a6bf6fa5e19ba6348eb673934a722a7ede2e7621306d18951e7cf2c73",
    ),
]


def test_rfc9497_oprf_vectors() -> None:
    secret, _ = oprf.derive_key_pair(SEED, KEY_INFO)
    assert secret.hex() == SK
    for value, blinded, evaluated, output in VECTORS:
        data = bytes.fromhex(value)
        result = oprf.blind(data, bytes.fromhex(BLIND))
        assert result.element.hex() == blinded
        assert oprf.blind_evaluate(secret, result.element).hex() == evaluated
        assert oprf.finalize(data, result.blind, bytes.fromhex(evaluated)).hex() == output


def test_token_does_not_depend_on_blind() -> None:
    secret, _ = oprf.derive_key_pair(SEED, b"anora-nazar:phone:1")
    data = oprf.oprf_input("phone", "998901234567")
    tokens = set()
    for _ in range(2):
        blinded = oprf.blind(data)
        tokens.add(oprf.token_of(oprf.finalize(data, blinded.blind, oprf.blind_evaluate(secret, blinded.element))))
    assert len(tokens) == 1
    with pytest.raises(oprf.OprfError):
        oprf.blind_evaluate(secret, bytes(32))


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        ("pinfl", " 31502901230017 ", "31502901230017"),
        ("phone", "+998 (90) 123-45-67", "998901234567"),
        ("phone", "901234567", "998901234567"),
        ("device", "  DEV-ABC ", "dev-abc"),
        ("card", "8600 1234 5678 9012", "8600123456789012"),
        ("supplier_inn", "301234567", "301234567"),
    ],
)
def test_normalize(kind: str, raw: str, expected: str) -> None:
    assert normalize(kind, raw) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "raw"),
    [
        ("pinfl", "3150290123001"),
        ("phone", "+7 901 234 56 78"),
        ("phone", "99890123456٧"),
        ("device", "   "),
        ("device", "x" * 129),
        ("card", "8600-1234-5678"),
        ("supplier_inn", "30123456a"),
    ],
)
def test_normalize_rejects(kind: str, raw: str) -> None:
    with pytest.raises(ValidationFailedError) as error:
        normalize(kind, raw)  # type: ignore[arg-type]
    assert error.value.code == "network_identifier_invalid"
