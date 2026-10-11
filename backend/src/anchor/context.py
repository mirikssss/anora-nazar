"""Зависимости процесса якоря."""

from dataclasses import dataclass

from anchor.settings import AnchorEnv
from shared.clock import Clock
from shared.crypto.signing import Verifier
from shared.db import Database


@dataclass
class AnchorContext:
    env: AnchorEnv
    db: Database
    clock: Clock
    verifier: Verifier
