"""Корень дерева Меркла по RFC 9162 (MTH): лист = H(0x00 ‖ d), узел = H(0x01 ‖ левый ‖ правый)."""

import hashlib
from collections.abc import Sequence


def _leaf(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _largest_power_of_two_below(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    if not leaves:
        return hashlib.sha256(b"").digest()
    if len(leaves) == 1:
        return _leaf(leaves[0])
    split = _largest_power_of_two_below(len(leaves))
    return _node(merkle_root(leaves[:split]), merkle_root(leaves[split:]))
