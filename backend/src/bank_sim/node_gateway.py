"""Вызовы узла от имени систем банка — у каждой свой ключ и свои права (заметка 11 «Ядро»)."""

from typing import Any
from uuid import UUID

import httpx

from bank_sim.settings import BankEnv
from shared.errors import ConfigurationError
from shared.http import ServiceClient


class NodeGateway:
    def __init__(self, env: BankEnv, timeout_seconds: float, transport: httpx.BaseTransport | None = None) -> None:
        def client(key: str, name: str) -> ServiceClient:
            return ServiceClient(env.node_url, key, timeout_seconds=timeout_seconds, name=name, transport=transport)

        self.conveyor = client(env.node_key_conveyor, "узел (конвейер)")
        self.core_banking = client(env.node_key_core_banking, "узел (АБС)")
        self.events = client(env.node_key_events, "узел (события)")
        self.realms = client(env.node_key_realms, "узел (песочницы)")
        self._env, self._transport = env, transport

    def create_realm(self, realm_id: UUID) -> dict[str, Any]:
        return self.realms.call("POST", "/v1/realms", json={"id": str(realm_id)})

    def delete_realm(self, realm_id: UUID) -> None:
        self.realms.call("DELETE", f"/v1/realms/{realm_id}")

    def assess(self, realm_id: UUID, body: dict[str, Any], key: str) -> dict[str, Any]:
        return self.conveyor.call("POST", "/v1/assessments", realm_id=realm_id, json=body, idempotency_key=key)

    def request_permit(self, realm_id: UUID, body: dict[str, Any], key: str) -> httpx.Response:
        return self.core_banking.request("POST", "/v1/permits", realm_id=realm_id, json=body, idempotency_key=key)

    def report_outcome(self, realm_id: UUID, operation_key: str, status: str) -> dict[str, Any]:
        return self.core_banking.call(
            "POST", "/v1/permits/outcomes", realm_id=realm_id, json={"operation_key": operation_key, "status": status}
        )

    def send_event(self, realm_id: UUID, envelope: dict[str, Any]) -> dict[str, Any]:
        return self.events.call("POST", "/v1/events", realm_id=realm_id, json=envelope)

    def send_watermarks(self, items: list[dict[str, Any]]) -> None:
        self.events.call("POST", "/v1/events/watermarks", json={"items": items})

    def history(self, timeout_seconds: float) -> ServiceClient:
        """Клиент прогона истории мира: отдельный ключ с правом history и долгий таймаут."""
        if self._env.node_key_history is None:
            raise ConfigurationError("Для прогона мира нужен BANK_SIM_NODE_KEY_HISTORY")
        return ServiceClient(
            self._env.node_url,
            self._env.node_key_history,
            timeout_seconds=timeout_seconds,
            name="узел (история)",
            transport=self._transport,
        )

    def close(self) -> None:
        for c in (self.conveyor, self.core_banking, self.events, self.realms):
            c.close()
