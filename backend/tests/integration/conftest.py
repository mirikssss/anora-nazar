"""Интеграционные тесты узла: настоящий PostgreSQL (отдельная база на тест), фиксированные часы,
системы банка и якорь — подменённые транспортом httpx."""

import json
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from node.background import NodeTasks
from node.context import NodeContext
from node.main import build_context, create_app
from node.modules.identity import service as identity
from node.modules.realms import service as realms
from node.settings import NodeEnv
from shared.clock import FixedClock
from shared.crypto.signing import generate_key_file
from shared.http import ServiceClient
from shared.migrations import upgrade

ADMIN_URL = os.environ.get("TEST_POSTGRES_URL")
MIGRATIONS = Path(__file__).parents[2] / "src" / "node" / "migrations"
KEYS = {
    "conveyor": "test-conveyor",
    "core_banking": "test-core-banking",
    "events": "test-events",
    "realms": "test-realms",
    "history": "test-history",
}
START = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)

pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="Интеграционные тесты: задайте TEST_POSTGRES_URL")


class FakeBank:
    """АБС и конвейер глазами узла: статусы операций и снимки заявок задаёт тест."""

    def __init__(self) -> None:
        self.operations: dict[str, str] = {}
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.notifications: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/v1/node/operations/"):
            status = self.operations.get(path.rsplit("/", 1)[-1])
            return (
                httpx.Response(404, json={"error": {"code": "operation_not_found"}})
                if status is None
                else httpx.Response(200, json={"status": status})
            )
        if path.startswith("/v1/node/applications/"):
            return httpx.Response(200, json=self.snapshots[path.split("/")[4]])
        if path == "/v1/node/notifications":
            self.notifications.extend(json.loads(request.content)["messages"])
            return httpx.Response(200, json={"accepted": 1})
        return httpx.Response(404)


class FakeAnchor:
    """Якорь: хранит корни; не даёт переписать уже принятую позицию."""

    def __init__(self) -> None:
        self.roots: dict[str, dict[int, str]] = {}

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            self.roots.setdefault(body["realm_id"], {})[body["seq"]] = body["merkle_root"]
            return httpx.Response(201, json=body)
        realm = request.url.params["realm_id"]
        items = [{"seq": s, "merkle_root": r} for s, r in sorted(self.roots.get(realm, {}).items())]
        return httpx.Response(200, json={"items": items})


class Node:
    def __init__(
        self,
        client: TestClient,
        ctx: NodeContext,
        clock: FixedClock,
        bank: FakeBank,
        anchor: FakeAnchor,
        world_id: UUID,
    ) -> None:
        self.client, self.ctx, self.clock, self.bank, self.anchor = client, ctx, clock, bank, anchor
        self.world_id = world_id
        self.tasks = NodeTasks(ctx)

    def new_sandbox(self) -> UUID:
        realm_id = uuid4()
        self.post("realms", "/v1/realms", None, json={"id": str(realm_id)}).raise_for_status()
        self.watermark(realm_id)
        return realm_id

    def watermark(self, realm_id: UUID, pending: int = 0, oldest: datetime | None = None) -> None:
        item = {
            "realm_id": str(realm_id),
            "producer": "bank-sim",
            "pending_count": pending,
            "oldest_pending_occurred_at": None if oldest is None else oldest.isoformat(),
            "reported_at": self.clock.now().isoformat(),
        }
        self.post("events", "/v1/events/watermarks", None, json={"items": [item]}).raise_for_status()

    def post(self, key: str, path: str, realm: UUID | None, *, json: Any, idem: str | None = None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {KEYS[key]}"}
        if realm is not None:
            headers["X-Realm-Id"] = str(realm)
        if idem is not None:
            headers["Idempotency-Key"] = idem
        return self.client.post(path, json=json, headers=headers)

    def staff(self, realm: UUID, user_code: str) -> dict[str, str]:
        token = self.client.post(
            "/v1/auth/demo-login", json={"user_code": user_code}, headers={"X-Realm-Id": str(realm)}
        ).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def assess(
        self, realm: UUID, external_id: str, snapshot: dict[str, Any], version: int = 1, point: str = "T1"
    ) -> dict[str, Any]:
        response = self.post(
            "conveyor",
            "/v1/assessments",
            realm,
            idem=str(uuid4()),
            json={
                "point": point,
                "application_id": external_id,
                "application_version": version,
                "occurred_at": self.clock.now().isoformat(),
                "snapshot": snapshot,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def permit(
        self,
        realm: UUID,
        external_id: str,
        snapshot: dict[str, Any],
        *,
        version: int = 1,
        key: str | None = None,
        amount: int | None = None,
    ) -> httpx.Response:
        return self.post(
            "core_banking",
            "/v1/permits",
            realm,
            idem=key or str(uuid4()),
            json={
                "application_id": external_id,
                "application_version": version,
                "operation_type": "disbursement",
                "tranche": 1,
                "amount": amount or snapshot["loan"]["amount"],
                "account": snapshot["disbursement_account"],
            },
        )

    def outcome(self, realm: UUID, key: str, status: str) -> httpx.Response:
        return self.post("core_banking", "/v1/permits/outcomes", realm, json={"operation_key": key, "status": status})

    def event(
        self,
        realm: UUID,
        external_id: str,
        version: int | None,
        type_: str = "application.version",
        payload: dict[str, Any] | None = None,
        entity_type: str = "application",
    ) -> dict[str, Any]:
        response = self.post(
            "events",
            "/v1/events",
            realm,
            json={
                "event_id": str(uuid4()),
                "source": "bank-sim.conveyor",
                "type": type_,
                "entity_type": entity_type,
                "entity_id": external_id,
                "entity_version": version,
                "occurred_at": self.clock.now().isoformat(),
                "schema_version": 1,
                "payload": payload or {},
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def sql(self, statement: str, **params: Any) -> list[Any]:
        with self.ctx.db.engine.begin() as conn:
            result = conn.execute(text(statement), params)
            return list(result) if result.returns_rows else []


@pytest.fixture
def node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Node]:
    assert ADMIN_URL is not None
    db_name = f"node_test_{uuid4().hex[:12]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"
    for name, value in KEYS.items():
        monkeypatch.setenv(f"NODE_API_KEY_{name.upper()}", value)
    key_path = tmp_path / "signing.key"
    generate_key_file(key_path)
    env = NodeEnv(
        database_url=url,
        signing_key_path=key_path,
        session_secret="test-secret",
        index_key="test-index",
        bank_sim_url="http://bank",
        bank_sim_api_key="k",
        anchor_url="http://anchor",
        anchor_api_key="k",
    )
    upgrade(MIGRATIONS, url)
    clock, bank, anchor = FixedClock(START), FakeBank(), FakeAnchor()
    ctx = build_context(env, clock)
    ctx.bank = _client("http://bank", bank.handle)
    ctx.anchor = _client("http://anchor", anchor.handle)
    with ctx.db.transaction() as session:
        world_id = realms.ensure_world(session, clock.now())
        identity.seed(session, env.seeds_dir)
    with TestClient(create_app(ctx, run_background=False)) as client:
        yield Node(client, ctx, clock, bank, anchor, world_id)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{db_name}" WITH (FORCE)'))
    admin.dispose()


def _client(base_url: str, handler: Callable[[httpx.Request], httpx.Response]) -> ServiceClient:
    return ServiceClient(base_url, "k", timeout_seconds=5, name="test", transport=httpx.MockTransport(handler))


def online(
    pinfl: str,
    phone: str,
    *,
    device: str | None = None,
    address: str | None = None,
    employer: str | None = None,
    employee: str | None = "EMP-01-1",
    branch: str = "BR-01",
    amount: int = 30_000_000,
    self_ban: str = "none",
) -> dict[str, Any]:
    applicant: dict[str, Any] = {"pinfl": pinfl, "phone": phone}
    for field, value in (("device_id", device), ("address", address), ("employer_inn", employer)):
        if value is not None:
            applicant[field] = value
    return {
        "channel": "online",
        "branch_id": branch,
        "employee_id": employee,
        "applicant": applicant,
        "loan": {"amount": amount, "term_months": 12},
        "disbursement_account": f"ACC-{pinfl[-6:]}",
        "program": None,
        "session_refs": [],
        "mandatory_checks": {"self_ban": self_ban, "bureau": "free", "biometry": "passed", "phone_owner_match": True},
    }
