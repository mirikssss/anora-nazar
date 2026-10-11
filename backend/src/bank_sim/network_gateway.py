"""Оператор сети глазами имитатора: кредиторы Б и В со своими ключами (тот же клиент OPRF, что у узла) и служебный
ключ стенда — удаление контура песочницы и сбой «сеть недоступна»."""

from uuid import UUID

import httpx

from bank_sim.settings import BankEnv
from shared.errors import ConfigurationError
from shared.http import ServiceClient
from shared.network.client import NetworkClient


class NetworkGateway:
    def __init__(self, env: BankEnv, url: str, timeout_seconds: float, transport: httpx.BaseTransport | None) -> None:
        self._url, self._timeout, self._transport = url, timeout_seconds, transport
        self._keys = {"B": env.network_key_b, "C": env.network_key_c}
        self._history_keys = {"B": env.network_key_b_history, "C": env.network_key_c_history}
        self._lenders = {code: self._client(code, key) for code, key in self._keys.items() if key}
        self._admin = (
            None
            if env.network_key_admin is None
            else ServiceClient(
                url, env.network_key_admin, timeout_seconds=timeout_seconds, name="оператор сети", transport=transport
            )
        )

    @classmethod
    def from_env(
        cls, env: BankEnv, timeout_seconds: float, transport: httpx.BaseTransport | None = None
    ) -> "NetworkGateway | None":
        """Сеть — отдельный адаптер: без адреса оператора имитатор работает без неё."""
        return None if env.network_url is None else cls(env, env.network_url, timeout_seconds, transport)

    def _client(self, code: str, key: str, timeout_seconds: float | None = None) -> NetworkClient:
        return NetworkClient(
            self._url,
            key,
            timeout_seconds=timeout_seconds or self._timeout,
            name=f"оператор сети (кредитор {code})",
            transport=self._transport,
        )

    def lender(self, code: str) -> NetworkClient:
        client = self._lenders.get(code)
        if client is None:
            raise ConfigurationError(f"Нет ключа кредитора {code} у оператора сети (BANK_SIM_NETWORK_KEY_{code})")
        return client

    def history_lender(self, code: str, timeout_seconds: float) -> NetworkClient:
        """Клиент прогона истории: право history, received_at из события, долгий таймаут."""
        key = self._history_keys.get(code)
        if not key:
            raise ConfigurationError(f"Для прогона мира нужен BANK_SIM_NETWORK_KEY_{code}_HISTORY")
        return self._client(code, key, timeout_seconds)

    def _admin_client(self) -> ServiceClient:
        if self._admin is None:
            raise ConfigurationError("Нет служебного ключа стенда у оператора сети (BANK_SIM_NETWORK_KEY_ADMIN)")
        return self._admin

    def delete_realm(self, realm_id: UUID) -> None:
        self._admin_client().call("DELETE", f"/v1/realms/{realm_id}")

    def set_outage(self, realm_id: UUID, active: bool) -> None:
        self._admin_client().call("PUT", f"/v1/demo/realms/{realm_id}/outage", json={"active": active})

    def close(self) -> None:
        for client in self._lenders.values():
            client.close()
        if self._admin is not None:
            self._admin.close()
