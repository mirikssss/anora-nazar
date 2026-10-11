"""Зависимости процесса узла: база, часы, ключ подписи, политика, клиенты других сервисов."""

from dataclasses import dataclass

from node.modules.decisions.service import AssessContext
from node.modules.ingest.service import IntakeContext
from node.modules.policy.service import PolicyRegistry
from node.settings import NodeConfig, NodeEnv
from shared.clock import Clock
from shared.crypto.signing import Signer
from shared.db import Database
from shared.http import ServiceClient
from shared.idempotency import IdempotencyStore


@dataclass
class NodeContext:
    env: NodeEnv
    config: NodeConfig
    db: Database
    clock: Clock
    signer: Signer
    policies: PolicyRegistry
    idempotency: IdempotencyStore
    bank: ServiceClient
    anchor: ServiceClient

    @property
    def index_key(self) -> bytes:
        return self.env.index_key.encode("utf-8")

    def intake(self) -> IntakeContext:
        return IntakeContext(
            policy=self.policies.active.policy, index_key=self.index_key, config=self.config, clock=self.clock
        )

    def assessing(self) -> AssessContext:
        return AssessContext(intake=self.intake(), bundle=self.policies.active, idempotency=self.idempotency)
