"""Зависимости процесса оператора сети."""

from dataclasses import dataclass

from network_operator.callbacks import CallbackSender
from network_operator.modules.oprf.domain import KeyRing
from network_operator.settings import OperatorConfig, OperatorEnv
from shared.clock import Clock
from shared.db import Database


@dataclass
class OperatorContext:
    env: OperatorEnv
    config: OperatorConfig
    db: Database
    clock: Clock
    keys: KeyRing
    callbacks: CallbackSender
