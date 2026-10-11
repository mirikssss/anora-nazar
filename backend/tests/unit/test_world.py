"""Генератор мира: воспроизводимость, порядок истории, контракт снимка, типологии, поздние факты, связи колец."""

from collections import defaultdict
from datetime import timedelta

import pytest

from shared.contracts.application import ApplicationSnapshot
from shared.contracts.history import HistoryAssessment, HistoryEvent
from world import DEFAULT_PARAMS_PATH, ApplicationTruth, World, generate, load_params

PARAMS = load_params(DEFAULT_PARAMS_PATH, scale=0.05)
COMPARED_ITEMS = 1000


@pytest.fixture(scope="module")
def world() -> World:
    return generate(PARAMS)


def snapshots(world: World) -> dict[str, ApplicationSnapshot]:
    return {
        item.application_id: item.snapshot
        for item in world.history
        if isinstance(item, HistoryAssessment) and item.application_version == 1
    }


def events(world: World, event_type: str) -> list[HistoryEvent]:
    return [item for item in world.history if isinstance(item, HistoryEvent) and item.envelope.type == event_type]


def rings(world: World) -> list[tuple[ApplicationTruth, list[ApplicationSnapshot]]]:
    by_app = snapshots(world)
    members: dict[str, list[ApplicationSnapshot]] = defaultdict(list)
    truths: dict[str, ApplicationTruth] = {}
    for app_id, truth in world.truth.items():
        if truth.typology == "F2" and truth.scheme_key is not None:
            members[truth.scheme_key].append(by_app[app_id])
            truths[truth.scheme_key] = truth
    return [(truths[key], group) for key, group in members.items()]


def identity(snapshot: ApplicationSnapshot, kind: str) -> str | None:
    applicant = snapshot.applicant
    return {"phone": applicant.phone, "device": applicant.device_id, "address": applicant.address}[kind]


def test_same_params_give_same_world(world):
    again = generate(PARAMS)
    assert len(again.history) == len(world.history)
    assert again.history[:COMPARED_ITEMS] == world.history[:COMPARED_ITEMS]
    assert again.truth == world.truth


def test_history_is_sorted_by_received_at(world):
    received = [item.received_at for item in world.history]
    assert received == sorted(received)


def test_every_assessment_passes_snapshot_contract(world):
    assessments = [item for item in world.history if isinstance(item, HistoryAssessment)]
    assert assessments
    for item in assessments:
        ApplicationSnapshot.model_validate(item.snapshot.model_dump())
        assert world.truth[item.application_id].lender == PARAMS.applications.lender


def test_all_typologies_present_with_plausible_share(world):
    by_app = snapshots(world)
    online = sum(1 for snapshot in by_app.values() if snapshot.channel == "online")
    program = len(by_app) - online
    fraud = PARAMS.fraud
    expected = (
        fraud.f1.share_of_online * online
        + fraud.f2.share_of_applications * (online + program)
        + fraud.f3.share_of_program * program
    ) / len(by_app)
    node_truth = [world.truth[app_id] for app_id in by_app]
    assert {"F1", "F2", "F3"} <= {truth.typology for truth in node_truth}
    actual = sum(1 for truth in node_truth if truth.typology is not None) / len(node_truth)
    assert expected / 3 <= actual <= expected * 3


def test_late_facts_exist(world):
    incidents = events(world, "incident.recorded")
    assert any(item.received_at - item.envelope.occurred_at > timedelta(days=1) for item in incidents)
    contributions = events(world, "inps.contributions")
    corrections = [item for item in contributions if item.envelope.entity_version == 2]
    assert corrections
    originals = {item.envelope.entity_id: item for item in contributions if item.envelope.entity_version == 1}
    for correction in corrections:
        assert originals[correction.envelope.entity_id].received_at < correction.received_at


def test_identity_rings_share_identifiers(world):
    identity_rings = [(truth, group) for truth, group in rings(world) if truth.shared_identities]
    assert identity_rings
    for truth, group in identity_rings:
        for kind in truth.shared_identities:
            values = [identity(snapshot, kind) for snapshot in group]
            assert len(set(values)) < len(values)


def test_coordination_rings_share_roles_but_no_identifiers(world):
    coordination = [(truth, group) for truth, group in rings(world) if not truth.shared_identities]
    assert coordination
    for truth, group in coordination:
        for kind in ("phone", "device", "address"):
            values = [value for snapshot in group if (value := identity(snapshot, kind)) is not None]
            assert len(set(values)) == len(values)
        roles = {
            "employee": {snapshot.employee_id for snapshot in group},
            "helper": {snapshot.program.helper_id for snapshot in group if snapshot.program},
            "supplier": {snapshot.program.supplier_inn for snapshot in group if snapshot.program},
        }
        assert truth.shared_roles
        assert all(len(roles[role]) == 1 for role in truth.shared_roles)
