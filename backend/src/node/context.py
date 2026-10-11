"""Зависимости процесса узла: база, часы, ключ подписи, политика, клиенты других сервисов."""

from dataclasses import dataclass

from node.modules.cases.domain import CasesConfig
from node.modules.cases.service import CaseContext
from node.modules.consortium.service import NetworkContext
from node.modules.decisions.service import AssessContext
from node.modules.ingest.service import IntakeContext
from node.modules.policy.service import PolicyRegistry
from node.modules.scoring.service import ModelCache
from node.modules.scoring.training.config import TrainingConfig
from node.modules.verification.domain import VerificationConfig
from node.modules.verification.service import VerificationContext
from node.settings import NodeConfig, NodeEnv
from shared.clock import Clock
from shared.crypto.signing import Signer
from shared.db import Database
from shared.http import ServiceClient
from shared.idempotency import IdempotencyStore
from shared.network.client import NetworkClient


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
    models: ModelCache
    cases_config: CasesConfig
    verification_config: VerificationConfig
    training_config: TrainingConfig
    network_client: NetworkClient | None = None  # адрес оператора сети не задан — сеть «недоступна»
    network_history: NetworkClient | None = None  # право history: ответы на прошлые моменты для обучения

    @property
    def index_key(self) -> bytes:
        return self.env.index_key.encode("utf-8")

    def case_context(self) -> CaseContext:
        return CaseContext(
            config=self.cases_config,
            node=self.config,
            policy=self.policies.active.policy,
            network=self.network(),
            policies=self.policies,
        )

    def network(self) -> NetworkContext:
        return NetworkContext(
            client=self.network_client,
            history=self.network_history,
            index_key=self.index_key,
            outbox=self.config.outbox,
        )

    def intake(self) -> IntakeContext:
        return IntakeContext(
            policy=self.policies.active.policy,
            index_key=self.index_key,
            config=self.config,
            clock=self.clock,
            verification=VerificationContext(config=self.verification_config, cases=self.case_context()),
        )

    def assessing(self) -> AssessContext:
        return AssessContext(
            intake=self.intake(),
            policies=self.policies,
            idempotency=self.idempotency,
            models=self.models,
            cases=self.case_context(),
            verification=self.verification_config,
            network=self.network(),
        )
