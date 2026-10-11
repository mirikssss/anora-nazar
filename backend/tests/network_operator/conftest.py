"""Оператор сети на настоящем PostgreSQL (отдельная база на тест), фиксированные часы; кредиторы ходят через
общий NetworkClient, уведомления узлу уходят на заглушку."""

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from network_operator.background import OperatorTasks
from network_operator.context import OperatorContext
from network_operator.main import build_context, create_app
from network_operator.modules.clients import service as clients
from network_operator.settings import OperatorEnv
from shared.clock import FixedClock
from shared.migrations import upgrade
from shared.network.client import NetworkClient

ADMIN_URL = os.environ.get("TEST_POSTGRES_URL")
MIGRATIONS = Path(__file__).parents[2] / "src" / "network_operator" / "migrations"
KEYS = {
    "OPERATOR_API_KEY_A": "key-a",
    "OPERATOR_API_KEY_A_HISTORY": "key-a-history",
    "OPERATOR_API_KEY_B": "key-b",
    "OPERATOR_API_KEY_B_HISTORY": "key-b-history",
    "OPERATOR_API_KEY_C": "key-c",
    "OPERATOR_API_KEY_C_HISTORY": "key-c-history",
    "OPERATOR_API_KEY_BANK_SIM": "key-bank-sim",
    "OPERATOR_CALLBACK_URL_A": "http://node",
    "OPERATOR_CALLBACK_KEY_A": "key-callback-a",
}
START = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
FORWARDED_HEADERS = ("authorization", "x-realm-id", "content-type")

pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="Интеграционные тесты: задайте TEST_POSTGRES_URL")


class FakeNode:
    """Колбэк кредитора A: запоминает уведомления с заголовками."""

    def __init__(self) -> None:
        self.received: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.received.append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("authorization"),
                "realm": request.headers.get("x-realm-id"),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(200, json={"accepted": True})


class Operator:
    def __init__(self, http: TestClient, ctx: OperatorContext, clock: FixedClock, node: FakeNode) -> None:
        self.http, self.ctx, self.clock, self.node = http, ctx, clock, node
        self.tasks = OperatorTasks(ctx)

    def transport(self) -> httpx.MockTransport:
        """HTTP клиента сети — в приложение оператора в этом процессе."""

        def forward(request: httpx.Request) -> httpx.Response:
            headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARDED_HEADERS}
            response = self.http.request(request.method, request.url.path, content=request.content, headers=headers)
            return httpx.Response(response.status_code, content=response.content, headers=response.headers)

        return httpx.MockTransport(forward)

    def lender(self, key_env: str) -> NetworkClient:
        return NetworkClient("http://operator", KEYS[key_env], timeout_seconds=5, transport=self.transport())

    def admin(self, method: str, path: str, body: Any = None) -> httpx.Response:
        return self.http.request(
            method, path, json=body, headers={"Authorization": f"Bearer {KEYS['OPERATOR_API_KEY_BANK_SIM']}"}
        )


@pytest.fixture
def operator(monkeypatch: pytest.MonkeyPatch) -> Iterator[Operator]:
    assert ADMIN_URL is not None
    db_name = f"operator_test_{uuid4().hex[:12]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    env = OperatorEnv(database_url=url, oprf_seed="a3" * 32, demo_mode=True)
    upgrade(MIGRATIONS, url)
    clock, node = FixedClock(START), FakeNode()
    ctx = build_context(env, clock, callback_transport=httpx.MockTransport(node.handle))
    with ctx.db.transaction() as session:
        clients.seed(session, env.seeds_dir)
    with TestClient(create_app(ctx, run_background=False)) as http:
        yield Operator(http, ctx, clock, node)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{db_name}" WITH (FORCE)'))
    admin.dispose()
