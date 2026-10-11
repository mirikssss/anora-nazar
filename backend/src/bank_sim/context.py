"""Зависимости процесса имитатора банка."""

from dataclasses import dataclass

from bank_sim.node_gateway import NodeGateway
from bank_sim.settings import BankConfig, BankEnv
from shared.clock import Clock
from shared.crypto.signing import Verifier
from shared.db import Database


@dataclass
class BankContext:
    env: BankEnv
    config: BankConfig
    db: Database
    clock: Clock
    node: NodeGateway
    node_verifier: Verifier
