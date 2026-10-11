"""Доставка уведомлений кредиторам по HTTP: адрес и ключ колбэка — из окружения, заголовок контура — у песочницы."""

from uuid import UUID

import httpx

from network_operator.modules.clients.domain import Callback
from shared.contracts.network import MatchNotification

NOTIFICATIONS_PATH = "/v1/network/notifications"
REALM_HEADER = "X-Realm-Id"


class DeliveryError(Exception):
    """Кредитор не принял уведомление: повтор после паузы."""


class CallbackSender:
    def __init__(
        self, callbacks: dict[str, Callback], timeout_seconds: float, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._callbacks = callbacks
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def can_notify(self, lender: str) -> bool:
        return lender in self._callbacks

    def send(self, lender: str, realm_id: UUID | None, notification: MatchNotification) -> None:
        callback = self._callbacks.get(lender)
        if callback is None:
            raise DeliveryError(f"У кредитора {lender} нет адреса уведомлений")
        headers = {"Authorization": f"Bearer {callback.key}"}
        if realm_id is not None:
            headers[REALM_HEADER] = str(realm_id)
        try:
            response = self._client.post(
                callback.url + NOTIFICATIONS_PATH, json=notification.model_dump(mode="json"), headers=headers
            )
        except httpx.TransportError as exc:
            raise DeliveryError(f"Кредитор {lender} недоступен: {exc}") from exc
        if not response.is_success:
            raise DeliveryError(f"Кредитор {lender} ответил {response.status_code}")

    def close(self) -> None:
        self._client.close()
