"""Клиент оператора сети кредиторов (network-contract-1): токенизация через OPRF, события, счётчики, результаты.

Один клиент у узла (кредитор A) и у кредиторов Б и В в имитаторе банка. Недоступность оператора, ответы 5xx
(сбой или выключенный контур, код network_unavailable) и 429 (квота OPRF, код oprf_quota_exceeded) —
UpstreamUnavailableError: узел решает без сети с причиной «сеть недоступна» и не принимает отказ сети за зелёный.
Ответ 4xx — ошибка кредитора (ключ, права, формат): AppError с кодом оператора.
"""

from collections import defaultdict
from collections.abc import Iterator, Sequence
from typing import Any
from uuid import UUID

import httpx

from shared.contracts.network import (
    MAX_BATCH,
    ActivityEvent,
    ActivityIn,
    ActivityOut,
    ConfirmedIn,
    ConfirmedResult,
    CounterQuery,
    CounterResult,
    CountersIn,
    CountersOut,
    EvaluationIn,
    EvaluationOut,
    TokenKind,
    TokenRef,
)
from shared.errors import AppError, UpstreamUnavailableError
from shared.http import ServiceClient
from shared.network import oprf
from shared.network.normalize import normalize

TOO_MANY_REQUESTS = 429
SERVER_ERRORS = 500


def _chunks[T](items: Sequence[T]) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), MAX_BATCH):
        yield items[start : start + MAX_BATCH]


def _unavailable(status_code: int) -> bool:
    """Квота OPRF, сбой оператора и выключенный контур — для решения это одно: сеть не ответила."""
    return status_code == TOO_MANY_REQUESTS or status_code >= SERVER_ERRORS


def _bad_response(reason: str) -> UpstreamUnavailableError:
    return UpstreamUnavailableError("network_bad_response", "Оператор сети ответил не по контракту", {"reason": reason})


class NetworkClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float,
        name: str = "оператор сети",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = ServiceClient(base_url, api_key, timeout_seconds=timeout_seconds, name=name, transport=transport)

    def _call(self, method: str, path: str, realm_id: UUID | None, body: Any = None) -> dict[str, Any]:
        response = self._http.request(method, path, realm_id=realm_id, json=body)
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = None
        if response.is_success:
            if not isinstance(payload, dict):
                raise _bad_response("ответ не JSON-объект")
            return payload
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        exc = (UpstreamUnavailableError if _unavailable(response.status_code) else AppError)(
            str(error.get("code", "network_error")),
            str(error.get("message", f"Оператор сети вернул ошибку {response.status_code}")),
            dict(error.get("details", {})),
        )
        exc.status_code = response.status_code
        raise exc

    def tokenize(
        self, realm_id: UUID | None, items: list[tuple[TokenKind, str]]
    ) -> dict[tuple[TokenKind, str], TokenRef]:
        """Токены значений; ключ ответа — пара (тип, значение) как передана. Неверный формат — ошибка до сети."""
        normalized = {item: normalize(*item) for item in items}
        by_kind: dict[TokenKind, list[str]] = defaultdict(list)
        for (kind, _), value in normalized.items():
            if value not in by_kind[kind]:
                by_kind[kind].append(value)
        refs: dict[tuple[TokenKind, str], TokenRef] = {}
        for kind, values in by_kind.items():
            for chunk in _chunks(values):
                refs.update(self._evaluate(realm_id, kind, chunk))
        return {item: refs[(item[0], value)] for item, value in normalized.items()}

    def _evaluate(
        self, realm_id: UUID | None, kind: TokenKind, values: Sequence[str]
    ) -> dict[tuple[TokenKind, str], TokenRef]:
        inputs = [oprf.oprf_input(kind, v) for v in values]
        blinded = [oprf.blind(i) for i in inputs]
        body = EvaluationIn(kind=kind, blinded=[b.element.hex() for b in blinded])
        try:
            out = EvaluationOut.model_validate(
                self._call("POST", "/v1/oprf/evaluations", realm_id, body.model_dump(mode="json"))
            )
            if out.kind != kind or len(out.evaluated) != len(values):
                raise _bad_response("число или тип вычисленных элементов не совпадает с запросом")
            outputs = [
                oprf.finalize(i, b.blind, bytes.fromhex(e))
                for i, b, e in zip(inputs, blinded, out.evaluated, strict=True)
            ]
        except ValueError as exc:  # в том числе ValidationError и OprfError
            raise _bad_response(str(exc)) from exc
        return {
            (kind, value): TokenRef(kind=kind, key_version=out.key_version, token=oprf.token_of(output))
            for value, output in zip(values, outputs, strict=True)
        }

    def send_activity(self, realm_id: UUID | None, events: list[ActivityEvent]) -> ActivityOut:
        accepted, duplicates, conflicts, unknown = 0, 0, [], []
        for chunk in _chunks(events):
            raw = self._call(
                "POST", "/v1/activity/events", realm_id, ActivityIn(events=list(chunk)).model_dump(mode="json")
            )
            out = ActivityOut.model_validate(raw)
            accepted, duplicates = accepted + out.accepted, duplicates + out.duplicates
            conflicts += out.conflicts
            unknown += out.unknown_references
        return ActivityOut(accepted=accepted, duplicates=duplicates, conflicts=conflicts, unknown_references=unknown)

    def query(self, realm_id: UUID | None, queries: list[CounterQuery]) -> list[CounterResult]:
        results: list[CounterResult] = []
        for chunk in _chunks(queries):
            body = CountersIn(queries=list(chunk)).model_dump(mode="json")
            results += CountersOut.model_validate(self._call("POST", "/v1/counters/queries", realm_id, body)).results
        return results

    def send_confirmed(self, realm_id: UUID | None, results: list[ConfirmedResult]) -> None:
        for chunk in _chunks(results):
            body = ConfirmedIn(results=list(chunk)).model_dump(mode="json")
            self._call("POST", "/v1/confirmed/results", realm_id, body)

    def stats(self, realm_id: UUID | None) -> dict[str, Any]:
        return self._call("GET", "/v1/stats", realm_id)

    def health(self) -> bool:
        try:
            return self._http.request("GET", "/v1/system/health").is_success
        except UpstreamUnavailableError:
            return False

    def close(self) -> None:
        self._http.close()
