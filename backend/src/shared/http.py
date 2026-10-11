"""HTTP-клиент между сервисами: таймауты, ключ API, ключ идемпотентности, понятные ошибки."""

from typing import Any
from uuid import UUID

import httpx

from shared.errors import AppError, UpstreamUnavailableError


class ServiceClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float,
        name: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._name = name
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        realm_id: UUID | None = None,
        json: Any = None,
        idempotency_key: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if realm_id is not None:
            headers["X-Realm-Id"] = str(realm_id)
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        try:
            return self._client.request(method, path, json=json, headers=headers, params=params)
        except httpx.TransportError as exc:
            raise UpstreamUnavailableError(
                "upstream_unavailable", f"Сервис «{self._name}» недоступен", {"reason": str(exc)}
            ) from exc

    def call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Запрос, ожидающий успешный JSON. Ошибку другого сервиса передаёт дальше с его кодом."""
        response = self.request(method, path, **kwargs)
        body: dict[str, Any] = response.json() if response.content else {}
        if response.is_success:
            return body
        error = body.get("error", {}) if isinstance(body, dict) else {}
        exc = AppError(
            str(error.get("code", "upstream_error")),
            str(error.get("message", f"Сервис «{self._name}» вернул ошибку {response.status_code}")),
            dict(error.get("details", {})),
        )
        exc.status_code = response.status_code
        raise exc

    def close(self) -> None:
        self._client.close()
