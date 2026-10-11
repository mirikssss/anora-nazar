"""Эталонные графы индекса связей (ревью F): каждый случай из tests/golden/graphs прогоняется через узел."""

import zlib
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml

from node.modules.decisions import service as decisions
from node.modules.realms import service as realms
from tests.integration.conftest import START, Node, online

GRAPHS = Path(__file__).parents[1] / "golden" / "graphs"
CASES = [case for path in sorted(GRAPHS.glob("*.yaml")) for case in yaml.safe_load(path.read_text())["cases"]]
FIELDS = {"phone", "device", "address", "employer", "employee"}


class Builder:
    """Короткие обозначения из YAML → корректные снимки: свой ПИНФЛ и телефон у каждого нового человека."""

    def __init__(self) -> None:
        self.people: dict[str, int] = {}
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, int] = {}
        self.steps: dict[str, dict[str, Any]] = {}

    def original(self, app_id: str) -> dict[str, Any]:
        return self.steps[app_id]

    def person(self, key: str) -> int:
        return self.people.setdefault(key, len(self.people) + 1)

    def snapshot(self, app_id: str, step: dict[str, Any]) -> dict[str, Any]:
        number = self.person(str(step.get("person", app_id)))
        token = {f: step[f] for f in FIELDS if f in step}

        def digits(prefix: str, value: str, width: int) -> str:
            return prefix + str(zlib.crc32(value.encode()) % 10**width).zfill(width)

        phone = digits("99890", token["phone"], 7) if "phone" in token else f"99891{number:07d}"
        return online(
            f"3{number:013d}",
            phone,
            device=token.get("device"),
            address=token.get("address"),
            employer=digits("", token["employer"], 9) if "employer" in token else None,
            employee=token.get("employee"),
        )


def _graph(node: Node, realm: UUID, decision_id: str) -> dict[str, Any]:
    with node.ctx.db.transaction() as session:
        context = realms.resolve(session, realm, node.clock.now())
        graph: dict[str, Any] = decisions.get_record(session, context, UUID(decision_id)).record["inputs"]["graph"]
        return graph


def _check(graph: dict[str, Any], expect: dict[str, Any], label: str) -> None:
    actual = {
        "independent_rare_links": graph["independent_rare_links"],
        "group_applications": graph["group_applications"],
        "burst": graph["burst"],
        "coordination_flagged": sorted(c["role"] for c in graph["coordination"] if c["flagged"]),
    }
    for key, value in expect.items():
        assert actual[key] == value, f"{label}: {key} = {actual[key]}, ожидалось {value}"


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_graph(node: Node, case: dict[str, Any]) -> None:
    realm, build = node.new_sandbox(), Builder()
    for order, step in enumerate(case["steps"]):
        repeat, every = int(step.get("repeat", 1)), int(step.get("every_days", 0))
        for i in range(repeat):
            node.clock.set(START + timedelta(days=step["day"] + i * every, minutes=order * 100 + i))
            app_id = f"{step['id']}{i + 1}" if repeat > 1 else step.get("id") or step["reassess"]
            if "reassess" in step:
                changed = {f: step[f] for f in FIELDS if f in step}
                if changed:
                    build.versions[app_id] += 1
                    build.snapshots[app_id] = build.snapshot(app_id, {**build.original(app_id), **changed})
            else:
                build.versions[app_id], build.steps[app_id] = 1, step
                build.snapshots[app_id] = build.snapshot(app_id, step)
            decision = node.assess(realm, app_id, build.snapshots[app_id], version=build.versions[app_id])
        if "expect" in step:
            _check(_graph(node, realm, decision["decision_id"]), step["expect"], f"{case['name']}, шаг {order + 1}")
