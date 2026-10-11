"""Каталог текстов: текст есть у каждого кода из источников; заёмщику не уходят формулировки для сотрудника."""

import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from node.modules.decisions.domain import STOP_BY_NORM
from node.modules.features.catalog import PASSPORTS
from node.modules.policy.reasons import Level, ReasonSource
from node.modules.texts import service
from node.modules.texts.api import router
from node.modules.texts.domain import missing_texts
from node.settings import PACKAGE_DIR, load_config
from shared.config import load_yaml
from shared.contracts.transfers import RecommendedAction
from shared.errors import install_error_handlers

NODE_DIR = Path(service.__file__).parents[2]
RULES_DIR = NODE_DIR / "modules" / "policy" / "rules"
CONFIG_DIR = NODE_DIR / "config"

# Кодов ещё нет в коде узла: списки — из постановки (Блок 4, Блок 5).
DATA_SOURCES = ("bank", "client", "network")
CASE_STATUSES = ("open", "in_progress", "escalated", "closed")
HOLD_STATUSES = ("active", "released")
CLIENT_SCREENS = ("approved", "intent_check", "pause", "under_review", "stopped", "cancelled")
FORBIDDEN_FOR_CLIENT = re.compile(r"\bAI\b|скоринг|модел", re.IGNORECASE)  # Блок 5: этих слов заёмщик не видит

NODE_CONFIG = load_config(PACKAGE_DIR / "config" / "node.yaml")
ACTIVE = NODE_CONFIG.texts.active_catalog


def _required_codes() -> dict[str, set[str]]:
    reasons = {r["code"] for path in RULES_DIR.glob("reasons-*.yaml") for r in load_yaml(path)["reasons"]}
    actions = {STOP_BY_NORM}
    for path in RULES_DIR.glob("policy-*.yaml"):
        policy_actions = load_yaml(path)["actions"]
        actions |= {policy_actions["green"]} | {rule["action"] for rule in policy_actions["rules"]}
    cases = load_yaml(CONFIG_DIR / "cases.yaml")
    actions |= {action for queue in cases["queues"].values() for action in queue["actions"]}
    verification = load_yaml(CONFIG_DIR / "verification.yaml")
    actions |= {verification["check"], verification["escalation"]}
    return {
        "reasons": reasons,
        "features": set(PASSPORTS),
        "levels": set(get_args(Level)),
        "reason_sources": set(get_args(ReasonSource)),
        "data_sources": set(DATA_SOURCES),
        "actions": actions,
        "case_outcomes": set(cases["outcomes"]),
        "participant_actions": set(cases["participant_actions"]),
        "participant_roles": set(cases["participant_roles"]),
        "checklist_items": {item for items in cases["checklists"].values() for item in items},
        "benign_explanations": set(cases["benign"]),
        "queues": set(cases["queues"]),
        "case_statuses": set(CASE_STATUSES),
        "hold_statuses": set(HOLD_STATUSES),
        "verification_questions": {q["code"] for q in verification["questions"]},
        "verification_answers": {f"{q['code']}.{a['code']}" for q in verification["questions"] for a in q["answers"]},
        "transfer_actions": set(get_args(RecommendedAction)),
        "client_screens": set(CLIENT_SCREENS),
    }


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def test_every_source_code_has_text() -> None:
    assert missing_texts(service.catalog(ACTIVE).catalog, _required_codes()) == {}


def test_client_gets_no_staff_texts_or_feature_names() -> None:
    loaded = service.catalog(ACTIVE)
    catalog = loaded.catalog
    client = service.render(loaded, "client", "ru").model_dump()
    staff_only = {text.resolve("ru") for r in catalog.reasons.values() for text in (r.staff_title, r.staff_explanation)}
    staff_only |= {f.title.resolve("ru") for f in catalog.features.values()}

    assert "features" not in client
    assert set(_strings(client)) & staff_only == set()
    assert set(client["reasons"]) == set(catalog.reasons)
    for text in _strings({key: value for key, value in client.items() if key not in ("version", "hash", "lang")}):
        assert not FORBIDDEN_FOR_CLIENT.search(text), text


@pytest.mark.parametrize(("audience", "has_features"), [("staff", True), ("client", False)])
def test_api_returns_catalog_for_audience(audience: str, has_features: bool) -> None:
    app = FastAPI()
    app.state.ctx = SimpleNamespace(config=NODE_CONFIG)
    install_error_handlers(app)
    app.include_router(router)
    client = TestClient(app)

    body = client.get("/v1/texts", params={"audience": audience}).json()
    assert body["audience"] == audience
    assert body["version"] == service.catalog(ACTIVE).catalog.version
    assert ("features" in body) is has_features

    unsupported = client.get("/v1/texts", params={"audience": audience, "lang": "xx"})
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "unsupported_language"
