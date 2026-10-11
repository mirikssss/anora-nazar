"""Канонический JSON по RFC 8785: хеш не зависит от порядка ключей и форматирования чисел."""

import hashlib
from typing import Any

import rfc8785


def canonical_bytes(value: Any) -> bytes:
    return bytes(rfc8785.dumps(value))


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
