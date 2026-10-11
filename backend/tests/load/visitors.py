"""Нагрузочный прогон демо-стенда: N проверяющих одновременно, каждый в своей песочнице — как фронт.

Посетитель создаёт песочницу, входит в роли сотрудников демо-входом, подаёт свою заявку и проводит зачисление
через АБС, запускает все готовые сценарии имитатора, открывает очереди дел и журнал. Когда все закончили —
пытается прочитать и изменить чужие заявки, решения, дела, операции и журнал; затем сбрасывает песочницу.

Проверки: ни одного 5xx; чужое не видно и не меняется; сброс работает. Свои заявки всех посетителей подаются
с одним телефоном и устройством: связи между песочницами нет — ни пометок чужих заявок, ни причин графа.
Время решения считается по зелёным заявкам; по ним же АБС проводит зачисление.

    docker compose --profile test run --rm tests python -m tests.load.visitors --visitors 30
    ... python -m tests.load.visitors --gateway https://nazar.clusteros.co.uz   # через шлюз стенда
"""

import argparse
import asyncio
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx

# Роль сотрудника — по праву из API, коды пользователей берутся из /v1/staff/roles.
ROLE_PERMISSIONS = {"analyst": "cases.online.view", "control": "cases.group.view", "risk": "audit.view"}
QUEUES = {"analyst": "online", "control": "group"}
DESCRIPTION = "Нагрузочный прогон демо-стенда: N посетителей одновременно, каждый в своей песочнице"


@dataclass
class Sample:
    route: str
    status: int
    seconds: float


@dataclass
class Report:
    samples: list[Sample] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    green_decisions: list[float] = field(default_factory=list)
    levels: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def fail(self, visitor: int, message: str) -> None:
        self.failures.append(f"посетитель {visitor}: {message}")


@dataclass
class Visitor:
    number: int
    realm: str = ""
    tokens: dict[str, str] = field(default_factory=dict)
    applications: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    cases: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)

    @property
    def realm_headers(self) -> dict[str, str]:
        return {"X-Realm-Id": self.realm}

    def staff(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@dataclass(frozen=True)
class World:
    """Справочники стенда, как их получает фронт: сотрудники, сценарии, филиал для своей заявки."""

    users: dict[str, str]
    scenarios: list[str]
    branch: str
    employee: str
    shared_phone: str
    shared_device: str


class Stand:
    def __init__(self, node: httpx.AsyncClient, bank: httpx.AsyncClient, report: Report) -> None:
        self.services = {"node": node, "bank": bank}
        self.report = report

    async def call(
        self,
        method: str,
        service: str,
        path: str,
        route: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        started = time.perf_counter()
        response = await self.services[service].request(method, path, headers=headers, json=body, params=params)
        sample = Sample(f"{method} {service} {route}", response.status_code, time.perf_counter() - started)
        self.report.samples.append(sample)
        if response.status_code == 429:
            self.report.failures.append(f"лимит шлюза (429): {sample.route} — для прогона поднимите GATEWAY_API_*")
        return response


def _digits(count: int) -> str:
    return "".join(random.choices("0123456789", k=count))


def _draft(world: World) -> dict[str, Any]:
    return {
        "channel": "online",
        "branch_id": world.branch,
        "employee_id": world.employee,
        "applicant": {"pinfl": "3" + _digits(13), "phone": world.shared_phone, "device_id": world.shared_device},
        "loan": {"amount": random.randrange(5, 40) * 1_000_000, "term_months": 12},
        "disbursement_account": "8600" + _digits(12),
        "checks": {"biometry": "passed", "phone_owner_match": True},
    }


async def load_world(stand: Stand) -> World:
    roles = (await stand.call("GET", "node", "/v1/staff/roles", "/v1/staff/roles")).raise_for_status().json()
    users = {
        name: next(r["users"][0]["code"] for r in roles if permission in r["permissions"] and r["users"])
        for name, permission in ROLE_PERMISSIONS.items()
    }
    scenarios = [s["code"] for s in (await stand.call("GET", "bank", "/v1/scenarios", "/v1/scenarios")).json()]
    branches = (await stand.call("GET", "bank", "/v1/staff/branches", "/v1/staff/branches")).json()
    branch = next(b for b in branches if b["employees"])
    return World(users, scenarios, branch["id"], branch["employees"][0]["id"], "99890" + _digits(7), f"load-{uuid4()}")


async def start(stand: Stand, world: World, visitor: Visitor) -> None:
    """Как фронт: песочница при первом входе, затем токены ролей и справочники экранов."""
    sandbox = await stand.call("POST", "bank", "/v1/sandboxes", "/v1/sandboxes")
    visitor.realm = sandbox.raise_for_status().json()["realm_id"]
    for role, user in world.users.items():
        login = await stand.call(
            "POST",
            "node",
            "/v1/auth/demo-login",
            "/v1/auth/demo-login",
            headers=visitor.realm_headers,
            body={"user_code": user},
        )
        visitor.tokens[role] = login.raise_for_status().json()["token"]
    await stand.call("GET", "bank", "/v1/roles", "/v1/roles")
    await stand.call("GET", "node", "/v1/texts", "/v1/texts", headers=visitor.staff("analyst"))


def _remember(visitor: Visitor, application: dict[str, Any]) -> None:
    """Заявка конвейера (id) или участник сценария (application_id) и последнее решение узла по ней."""
    app_id = application.get("id") or application.get("application_id")
    if app_id:
        visitor.applications.append(app_id)
    decision = application.get("last_decision") or {}
    if decision.get("decision_id"):
        visitor.decisions.append(decision["decision_id"])


async def own_application(stand: Stand, world: World, visitor: Visitor) -> None:
    """Своя заявка и зачисление: АБС запрашивает разрешение у узла прямо перед проводкой."""
    started = time.perf_counter()
    created = await stand.call(
        "POST",
        "bank",
        "/v1/conveyor/applications",
        "/v1/conveyor/applications",
        headers=visitor.realm_headers,
        body=_draft(world),
    )
    seconds = time.perf_counter() - started
    if created.status_code != 201:
        stand.report.fail(visitor.number, f"своя заявка: {created.status_code} {created.text[:200]}")
        return
    application = created.json()
    _remember(visitor, application)
    decision = application.get("last_decision") or {}
    level = decision.get("level") or "нет решения"
    stand.report.levels[level] += 1
    graph = [r["code"] for r in decision.get("reasons", []) if r.get("source") == "graph"]
    if decision.get("marked_applications") or graph:
        stand.report.fail(visitor.number, f"связь через чужую песочницу: {decision.get('marked_applications')} {graph}")
    if level != "green":
        return
    stand.report.green_decisions.append(seconds)
    operation = await stand.call(
        "POST",
        "bank",
        "/v1/core-banking/operations",
        "/v1/core-banking/operations",
        headers=visitor.realm_headers,
        body={"application_id": application["id"], "operation_type": "disbursement"},
    )
    if operation.status_code != 201 or operation.json()["status"] != "executed":
        stand.report.fail(
            visitor.number, f"зачисление по зелёной заявке: {operation.status_code} {operation.text[:200]}"
        )
        return
    visitor.operations.append(operation.json()["operation_key"])


async def scenarios(stand: Stand, world: World, visitor: Visitor) -> None:
    for code in world.scenarios:
        run = await stand.call(
            "POST", "bank", f"/v1/scenarios/{code}/runs", "/v1/scenarios/{code}/runs", headers=visitor.realm_headers
        )
        if run.status_code != 201:
            stand.report.fail(visitor.number, f"сценарий {code}: {run.status_code} {run.text[:200]}")
            continue
        for application in run.json()["applications"]:
            _remember(visitor, application)
            if application.get("error"):
                stand.report.fail(visitor.number, f"сценарий {code}: ошибка участника {application['error']}")


async def staff_screens(stand: Stand, visitor: Visitor) -> None:
    """Очереди аналитика и внутреннего контроля, дело, решение, журнал риск-менеджера."""
    for role, queue in QUEUES.items():
        listed = await stand.call(
            "GET", "node", "/v1/cases", "/v1/cases", headers=visitor.staff(role), params={"queue": queue}
        )
        if listed.status_code != 200:
            stand.report.fail(visitor.number, f"очередь {queue}: {listed.status_code}")
            continue
        visitor.cases.extend(c["case_id"] for c in listed.json())
    for case_id in visitor.cases[:2]:
        await stand.call("GET", "node", f"/v1/cases/{case_id}", "/v1/cases/{id}", headers=visitor.staff("control"))
    if visitor.decisions:
        await stand.call(
            "GET",
            "node",
            f"/v1/decisions/{visitor.decisions[0]}",
            "/v1/decisions/{id}",
            headers=visitor.staff("analyst"),
        )
    await stand.call("GET", "node", "/v1/audit/records", "/v1/audit/records", headers=visitor.staff("risk"))
    await stand.call("GET", "node", "/v1/risk/overview", "/v1/risk/overview", headers=visitor.staff("risk"))


async def expect_hidden(stand: Stand, visitor: Visitor, what: str, response: httpx.Response) -> None:
    if response.status_code not in (403, 404):
        stand.report.fail(visitor.number, f"чужое доступно — {what}: {response.status_code} {response.text[:200]}")


async def isolation(stand: Stand, visitor: Visitor, other: Visitor) -> None:
    """Чужие id известны (утечка, подбор) — песочница посетителя их всё равно не видит и не меняет."""
    analyst, control = visitor.staff("analyst"), visitor.staff("control")
    for app_id in other.applications[:3]:
        await expect_hidden(
            stand,
            visitor,
            f"заявка узла {app_id}",
            await stand.call("GET", "node", f"/v1/applications/{app_id}", "/v1/applications/{id}", headers=analyst),
        )
        await expect_hidden(
            stand,
            visitor,
            f"заявка конвейера {app_id}",
            await stand.call(
                "GET",
                "bank",
                f"/v1/conveyor/applications/{app_id}",
                "/v1/conveyor/applications/{id}",
                headers=visitor.realm_headers,
            ),
        )
        await expect_hidden(
            stand,
            visitor,
            f"зачисление по чужой заявке {app_id}",
            await stand.call(
                "POST",
                "bank",
                "/v1/core-banking/operations",
                "/v1/core-banking/operations",
                headers=visitor.realm_headers,
                body={"application_id": app_id, "operation_type": "disbursement"},
            ),
        )
    for decision_id in other.decisions[:3]:
        await expect_hidden(
            stand,
            visitor,
            f"решение {decision_id}",
            await stand.call("GET", "node", f"/v1/decisions/{decision_id}", "/v1/decisions/{id}", headers=analyst),
        )
    for case_id in other.cases[:2]:
        await expect_hidden(
            stand,
            visitor,
            f"дело {case_id}",
            await stand.call("GET", "node", f"/v1/cases/{case_id}", "/v1/cases/{id}", headers=control),
        )
        await expect_hidden(
            stand,
            visitor,
            f"назначение дела {case_id}",
            await stand.call(
                "POST", "node", f"/v1/cases/{case_id}/assignment", "/v1/cases/{id}/assignment", headers=control
            ),
        )
    for key in other.operations[:1]:
        await expect_hidden(
            stand,
            visitor,
            f"операция АБС {key}",
            await stand.call(
                "GET",
                "bank",
                f"/v1/core-banking/operations/{key}",
                "/v1/core-banking/operations/{key}",
                headers=visitor.realm_headers,
            ),
        )
    await expect_hidden(
        stand,
        visitor,
        "токен сотрудника с чужой песочницей",
        await stand.call(
            "GET",
            "node",
            "/v1/cases",
            "/v1/cases",
            headers={**analyst, "X-Realm-Id": other.realm},
            params={"queue": "online"},
        ),
    )
    await expect_hidden(
        stand,
        visitor,
        "ключ системы заменён токеном сотрудника",
        await stand.call(
            "DELETE", "node", f"/v1/realms/{other.realm}", "/v1/realms/{id}", headers=visitor.staff("risk")
        ),
    )
    await own_lists_clean(stand, visitor, other)


async def own_lists_clean(stand: Stand, visitor: Visitor, other: Visitor) -> None:
    foreign = set(other.applications) | set(other.decisions) | set(other.cases)
    lists = [
        await stand.call(
            "GET",
            "node",
            "/v1/audit/records",
            "/v1/audit/records",
            headers=visitor.staff("risk"),
            params={"limit": 500},
        ),
        await stand.call(
            "GET", "bank", "/v1/conveyor/applications", "/v1/conveyor/applications", headers=visitor.realm_headers
        ),
        *[
            await stand.call(
                "GET", "node", "/v1/cases", "/v1/cases", headers=visitor.staff(role), params={"queue": queue}
            )
            for role, queue in QUEUES.items()
        ],
    ]
    text = " ".join(r.text for r in lists)
    leaked = sorted(i for i in foreign if i in text)
    if leaked:
        stand.report.fail(visitor.number, f"в своих списках и журнале чужие id: {leaked[:5]}")


async def reset(stand: Stand, world: World, visitor: Visitor) -> None:
    deleted = await stand.call(
        "DELETE", "bank", "/v1/sandboxes/current", "/v1/sandboxes/current", headers=visitor.realm_headers
    )
    if deleted.status_code != 204:
        stand.report.fail(visitor.number, f"сброс песочницы: {deleted.status_code} {deleted.text[:200]}")
        return
    after = [
        await stand.call(
            "GET", "bank", "/v1/conveyor/applications", "/v1/conveyor/applications", headers=visitor.realm_headers
        ),
        await stand.call(
            "GET", "node", "/v1/cases", "/v1/cases", headers=visitor.staff("analyst"), params={"queue": "online"}
        ),
        await stand.call(
            "POST",
            "node",
            "/v1/auth/demo-login",
            "/v1/auth/demo-login",
            headers=visitor.realm_headers,
            body={"user_code": world.users["analyst"]},
        ),
    ]
    alive = [r.request.url.path for r in after if r.status_code != 404]
    if alive:
        stand.report.fail(visitor.number, f"после сброса песочница ещё отвечает: {alive}")


async def visit(
    stand: Stand,
    world: World,
    visitor: Visitor,
    ready: asyncio.Barrier,
    checked: asyncio.Barrier,
    others: list[Visitor],
) -> None:
    try:
        await start(stand, world, visitor)
        await own_application(stand, world, visitor)
        await scenarios(stand, world, visitor)
        await staff_screens(stand, visitor)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        stand.report.fail(visitor.number, f"сценарий посетителя прерван: {exc!r}")
    await ready.wait()
    other = others[(visitor.number + 1) % len(others)]
    if visitor.tokens and other.realm and other is not visitor:
        try:
            await isolation(stand, visitor, other)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            stand.report.fail(visitor.number, f"проверка изоляции прервана: {exc!r}")
    await checked.wait()
    if visitor.tokens:
        try:
            await reset(stand, world, visitor)
        except httpx.HTTPError as exc:
            stand.report.fail(visitor.number, f"сброс прерван: {exc!r}")


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


def _ms(values: list[float]) -> str:
    if not values:
        return "—"
    return (
        f"p50 {_percentile(values, 0.5) * 1000:.0f} мс, p95 {_percentile(values, 0.95) * 1000:.0f} мс, "
        f"макс {max(values) * 1000:.0f} мс"
    )


def print_report(report: Report, visitors: int, wall: float) -> None:
    by_status: dict[str, int] = defaultdict(int)
    by_route: dict[str, list[float]] = defaultdict(list)
    for s in report.samples:
        by_status[f"{s.status // 100}xx"] += 1
        by_route[s.route].append(s.seconds)
    server_errors = [s for s in report.samples if s.status >= 500]
    print(
        f"\nПосетителей: {visitors}; запросов: {len(report.samples)} за {wall:.1f} с "
        f"({len(report.samples) / wall:.1f} в секунду)"
    )
    print("Ответы: " + ", ".join(f"{k} — {v}" for k, v in sorted(by_status.items())))
    print(f"Уровни своих заявок: {dict(report.levels)}")
    print(f"Решение по зелёной заявке (конвейер → узел → ответ): {_ms(report.green_decisions)}")
    print("\nМаршрут | запросов | время")
    for route, values in sorted(by_route.items()):
        print(f"{route} | {len(values)} | {_ms(values)}")
    if server_errors:
        print(f"\n5xx: {len(server_errors)}")
        for s in server_errors[:20]:
            print(f"  {s.status} {s.route}")
    print(f"\nНарушенных проверок: {len(report.failures)}")
    for failure in report.failures[:30]:
        print(f"  {failure}")


async def run(args: argparse.Namespace) -> int:
    node_url, bank_url = args.node_url, args.bank_url
    if args.gateway:
        node_url, bank_url = f"{args.gateway.rstrip('/')}/api/node", f"{args.gateway.rstrip('/')}/api/bank"
    if not node_url or not bank_url:
        raise SystemExit(
            "Задайте --gateway или --node-url и --bank-url (в контейнере tests — E2E_NODE_URL, E2E_BANK_SIM_URL)"
        )
    limits = httpx.Limits(max_connections=args.visitors * 4)
    report = Report()
    async with (
        httpx.AsyncClient(base_url=node_url, timeout=args.timeout, limits=limits) as node,
        httpx.AsyncClient(base_url=bank_url, timeout=args.timeout, limits=limits) as bank,
    ):
        stand = Stand(node, bank, report)
        world = await load_world(stand)
        visitors = [Visitor(i) for i in range(args.visitors)]
        ready, checked = asyncio.Barrier(len(visitors)), asyncio.Barrier(len(visitors))
        started = time.perf_counter()
        await asyncio.gather(*(visit(stand, world, v, ready, checked, visitors) for v in visitors))
        wall = time.perf_counter() - started
    print_report(report, args.visitors, wall)
    return 1 if report.failures or any(s.status >= 500 for s in report.samples) else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tests.load.visitors", description=DESCRIPTION)
    parser.add_argument("--visitors", type=int, default=30, help="сколько посетителей одновременно")
    parser.add_argument("--gateway", help="адрес шлюза стенда: /api/node и /api/bank")
    parser.add_argument("--node-url", default=os.environ.get("E2E_NODE_URL"))
    parser.add_argument("--bank-url", default=os.environ.get("E2E_BANK_SIM_URL"))
    parser.add_argument("--timeout", type=float, default=120.0, help="предел ожидания одного запроса, с")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
