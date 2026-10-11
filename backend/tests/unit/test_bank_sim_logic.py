"""Чистая логика имитатора банка: экран заёмщика, правило ТАФ, сиды персон и сценариев, участники запуска."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from random import Random
from typing import Any
from uuid import uuid4

import pytest

from bank_sim.modules.borrower_app.domain import BorrowerState, Notice, check_answers, reason_codes, screen
from bank_sim.modules.conveyor.schemas import ApplicationDraft
from bank_sim.modules.lenders.domain import LenderApplication
from bank_sim.modules.personas.service import load_borrowers
from bank_sim.modules.scenarios.domain import (
    ApplicationStep,
    BranchRef,
    HelperRef,
    ItemRef,
    LenderStep,
    ScenarioBook,
    ScenarioError,
    WorldRefs,
    application_drafts,
    cast,
    lender_applications,
    run_seed,
)
from bank_sim.modules.sources.domain import InpsProfile, inps_contributions, months_before
from bank_sim.modules.transfers.domain import NodeRecommendation, OwnRule, apply_own_rule, status_from_recommendation
from bank_sim.settings import PACKAGE_DIR, load_config
from shared.config import load_yaml

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
CONFIG = load_config(PACKAGE_DIR / "config" / "bank_sim.yaml")
RULES = CONFIG.borrower.screens
SEEDS = PACKAGE_DIR / "seeds"


def _decision(action: str, holds: Sequence[tuple[str, str]] = (), outcome: str = "assessed") -> dict[str, Any]:
    return {
        "outcome": outcome,
        "action": action,
        "holds": [{"hold_id": h, "required_check": c} for h, c in holds],
        "reasons": [
            {"code": "F1_NEW_DEVICE", "level": "yellow"},
            {"code": "SYSTEM_NO_MODEL", "level": None},
            {"code": "F1_NEW_DEVICE", "level": "yellow"},
        ],
    }


def _state(decision: dict[str, Any] | None, *notices: Notice, **overrides: Any) -> BorrowerState:
    base: dict[str, Any] = {
        "status": "assessed",
        "decision": decision,
        "notices": notices,
        "intent_answered": False,
        "pressure_reported_at": None,
    }
    return BorrowerState(**{**base, **overrides})


def _notice(topic: str, hold_id: str, check: str, at: datetime) -> Notice:
    return Notice(
        topic=topic, payload={"application_id": "APP-1", "hold_id": hold_id, "required_check": check}, received_at=at
    )


def test_borrower_screen_follows_decision_and_holds() -> None:
    assert screen(_state(_decision("continue")), RULES) == "approved"
    assert screen(_state(None), RULES) == "under_review"
    assert screen(_state(_decision("stop_by_norm", outcome="stopped_by_norm")), RULES) == "stopped"
    assert screen(_state(_decision("continue"), status="cancelled"), RULES) == "cancelled"

    yellow = _decision("intent_check", [("h1", "intent_check")])
    assert screen(_state(yellow), RULES) == "intent_check"
    assert screen(_state(yellow, intent_answered=True), RULES) == "under_review", "ответы ушли — ждём узел"
    released = _notice("hold.released", "h1", "intent_check", NOW)
    assert screen(_state(yellow, released, intent_answered=True), RULES) == "approved"
    escalated = _notice("hold.placed", "h2", "pause_for_call", NOW)
    assert screen(_state(yellow, escalated, intent_answered=True), RULES) == "pause", "пауза строже проверки"
    assert screen(_state(_decision("internal_review", [("h3", "internal_review")])), RULES) == "under_review"
    assert screen(_state(_decision("x", [("h4", "unknown_check")])), RULES) == "under_review"


def test_pressure_keeps_pause_until_analyst_releases() -> None:
    green = _decision("continue")
    assert screen(_state(green, pressure_reported_at=NOW), RULES) == "pause"
    earlier = _notice("hold.released", "h0", "intent_check", NOW - timedelta(minutes=1))
    assert screen(_state(green, earlier, pressure_reported_at=NOW), RULES) == "pause"
    placed = _notice("hold.placed", "h1", "pause_for_call", NOW + timedelta(seconds=1))
    later = _notice("hold.released", "h1", "pause_for_call", NOW + timedelta(minutes=30))
    assert screen(_state(green, placed, later, pressure_reported_at=NOW), RULES) == "approved"


def test_client_reason_codes_and_answers() -> None:
    assert reason_codes(_decision("intent_check")) == ["F1_NEW_DEVICE"]
    assert reason_codes(None) == []
    questions = {"purpose_own_need": {"yes_own", "no_other_person"}, "someone_instructs": {"no_one", "yes_someone"}}
    check_answers(questions, [("purpose_own_need", "yes_own"), ("someone_instructs", "no_one")])
    bad = [
        [("purpose_own_need", "yes_own")],
        [("purpose_own_need", "yes_own"), ("purpose_own_need", "no_other_person")],
        [("purpose_own_need", "yes_own"), ("someone_instructs", "maybe")],
        [("purpose_own_need", "yes_own"), ("someone_instructs", "no_one"), ("extra", "x")],
    ]
    for answers in bad:
        with pytest.raises(ValueError):
            check_answers(questions, answers)


def test_bank_antifraud_own_rule_and_node_recommendation() -> None:
    rule = OwnRule(window_hours=24, min_credit_share=0.5, new_recipient_only=True)
    credited = NOW - timedelta(hours=2)

    def holds(**kwargs: Any) -> bool:
        args: dict[str, Any] = {
            "amount": 10_000_000,
            "balance_before_credit": 500_000,
            "recipient_is_new": True,
            "credited_at": credited,
            "now": NOW,
        }
        return apply_own_rule(rule, **{**args, **kwargs}).hold

    assert holds()
    assert not holds(recipient_is_new=False), "знакомая карта"
    assert not holds(amount=900_000), "почти всё — свои деньги: доля кредита 0,44"
    assert not holds(credited_at=NOW - timedelta(hours=30)), "вне окна после зачисления"
    assert (
        apply_own_rule(
            rule, amount=1000, balance_before_credit=2000, recipient_is_new=True, credited_at=credited, now=NOW
        ).credit_share
        == 0
    )

    def recommendation(action: str) -> NodeRecommendation:
        return NodeRecommendation(recommendation_id="r", level="red", recommended_action=action, reasons=[])

    assert status_from_recommendation(recommendation("hold_until_confirmed")) == "held"
    assert status_from_recommendation(recommendation("allow")) == "executed"
    assert status_from_recommendation(recommendation("something_new")) is None
    assert status_from_recommendation(None) is None


def test_source_facts_from_profile() -> None:
    assert months_before(date(2026, 1, 15), 3) == ["2025-10", "2025-11", "2025-12"]
    jump = InpsProfile.model_validate(
        {"monthly": 1000, "months": 4, "jump": {"months": 2, "factor": 3, "voluntary": True}}
    )
    rows = inps_contributions("41403659010270", jump, date(2026, 10, 11)).months
    assert [(r.month, r.amount, r.voluntary) for r in rows] == [
        ("2026-06", 1000, False),
        ("2026-07", 1000, False),
        ("2026-08", 1000, False),
        ("2026-08", 2000, True),
        ("2026-09", 1000, False),
        ("2026-09", 2000, True),
    ]


def test_persona_seeds_are_in_world_formats() -> None:
    personas = load_borrowers(SEEDS)
    assert 6 <= len(personas) <= 8
    assert len({p.profile.applicant.pinfl for p in personas}) == len(personas)
    assert any(p.code == "muhabbat" for p in personas)


REFS = WorldRefs(
    helpers=tuple(HelperRef(f"HLP-001-{m:02d}", "Ташкент, район 1", f"махалля {m}") for m in range(1, 4)),
    branches=(BranchRef("BR-01", "Район 1", "EMP-01-1"), BranchRef("BR-01-1", "Ташкент, район 1", "EMP-01-1-1")),
    online_branch=CONFIG.borrower.branch_id,
    catalog={"cow": ItemRef("head", 12_000_000)},
    address_format="{district}, {mahalla}, дом {house}",
    operator_codes=("90", "93"),
    pinfl_district_codes=CONFIG.scenarios.pinfl_district_codes,
    house_numbers=CONFIG.scenarios.house_numbers,
    card_prefixes=tuple(CONFIG.scenarios.card_prefixes),
)


def _drafts(book: ScenarioBook, code: str, seed: str, refs: WorldRefs = REFS) -> list[ApplicationDraft]:
    spec = book.find(code)
    assert spec is not None
    crew = cast(spec, refs, Random(seed))
    return [
        ApplicationDraft.model_validate(raw)
        for step in spec.steps
        if isinstance(step, ApplicationStep)
        for _, raw in application_drafts(step, crew, refs)
    ]


def test_scenarios_build_valid_applications_with_fresh_identities() -> None:
    book = ScenarioBook.model_validate(load_yaml(SEEDS / "scenarios.yaml"))
    assert {s.zone for s in book.scenarios} >= {1, 2, 3}
    realm = uuid4()
    for spec in book.scenarios:
        first = _drafts(book, spec.code, run_seed(realm, 1))
        assert first == _drafts(book, spec.code, run_seed(realm, 1)), "запуск детерминирован"
        second = _drafts(book, spec.code, run_seed(realm, 2))
        assert not {d.applicant.pinfl for d in first} & {d.applicant.pinfl for d in second}, "новые люди на запуск"

    ring = _drafts(book, "zone2_ring", run_seed(realm, 1))
    assert len({d.applicant.pinfl for d in ring}) == 5
    assert len({d.applicant.device_id for d in ring}) == 1 and len({d.applicant.address for d in ring}) == 1
    linked = _drafts(book, "zone2_second_branch", run_seed(realm, 1))
    assert linked[0].branch_id != linked[1].branch_id and linked[0].applicant.phone == linked[1].applicant.phone

    (program,) = _drafts(book, "zone3_overpriced_livestock", run_seed(realm, 1))
    assert program.program is not None and program.program.unit_price == 24_000_000
    assert program.applicant.registration_mahalla != program.program.helper_mahalla
    assert program.loan.amount == 48_000_000 and program.branch_id == "BR-01-1"


def test_program_scenario_needs_loaded_world() -> None:
    book = ScenarioBook.model_validate(load_yaml(SEEDS / "scenarios.yaml"))
    empty = WorldRefs(**{**REFS.__dict__, "helpers": ()})
    with pytest.raises(ScenarioError):
        _drafts(book, "zone3_overpriced_livestock", "seed", empty)
    assert len(_drafts(book, "zone1_pressure", "seed", empty)) == 1, "онлайн-сценарий работает и без мира"


def test_network_scenarios_share_identifiers_only_through_other_lenders() -> None:
    book = ScenarioBook.model_validate(load_yaml(SEEDS / "scenarios.yaml"))
    realm, now = uuid4(), datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

    def elsewhere(code: str) -> tuple[list[LenderApplication], list[ApplicationDraft]]:
        spec = book.find(code)
        assert spec is not None
        crew = cast(spec, REFS, Random(run_seed(realm, 1)))
        apps = [
            app
            for number, step in enumerate(spec.steps, start=1)
            if isinstance(step, LenderStep)
            for app in lender_applications(step, crew, now, realm, number)
        ]
        return apps, _drafts(book, code, run_seed(realm, 1))

    others, (client,) = elsewhere("network_links_elsewhere")
    assert {a.phone for a in others} == {client.applicant.phone} and len({a.device_id for a in others}) == 1
    assert client.applicant.pinfl not in {a.pinfl for a in others} and len({a.pinfl for a in others}) == 2
    series, (same,) = elsewhere("network_pinfl_series")
    assert {a.pinfl for a in series} == {same.applicant.pinfl} and min(a.occurred_at for a in series) > now - timedelta(
        hours=1
    )
    cards, _ = elsewhere("network_card_transfer")
    assert len({a.transfer.card for a in cards if a.transfer}) == 1 and all(a.issued_at for a in cards)
