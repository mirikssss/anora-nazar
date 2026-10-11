"""Мир → история через узел → обучение → выпуск вторым подписантом → оценка с моделью; point-in-time."""

from datetime import timedelta
from typing import Any

from node.modules.features import service as features
from node.modules.realms import service as realms
from node.modules.scoring.training import pipeline
from node.modules.scoring.training.config import load_training_config
from shared.contracts.application import ApplicationSnapshot
from shared.contracts.history import HistoryAssessment
from tests.integration.conftest import START, Node, online
from world import DEFAULT_PARAMS_PATH, WorldParams, generate, load_params


def _dense(params: WorldParams) -> WorldParams:
    """Фикстура теста механики: больше мошенничества и все случаи раскрыты — чтобы в крошечном мире были метки
    и в обучении, и в окне проверки. Параметры стенда не меняются."""
    fraud = params.fraud.model_copy(
        update={
            "f1": params.fraud.f1.model_copy(update={"share_of_online": 0.05}),
            "f2": params.fraud.f2.model_copy(update={"share_of_applications": 0.05}),
            "f3": params.fraud.f3.model_copy(update={"share_of_program": 0.15}),
        }
    )
    outcomes = params.outcomes.model_copy(
        update={k: getattr(params.outcomes, k).model_copy(update={"detected": 1.0}) for k in ("f1", "f2", "f3")}
    )
    return params.model_copy(update={"fraud": fraud, "outcomes": outcomes})


def _replay_world(node: Node, scale: float) -> list[HistoryAssessment]:
    world = generate(_dense(load_params(DEFAULT_PARAMS_PATH, scale)))
    for start in range(0, len(world.history), 500):
        items = [item.model_dump(mode="json") for item in world.history[start : start + 500]]
        response = node.post("history", "/v1/history/batches", None, json={"items": items})
        assert response.status_code == 200, response.text
    return [i for i in world.history if isinstance(i, HistoryAssessment)]


def _passes_mandatory(snapshot: ApplicationSnapshot) -> bool:
    checks = snapshot.mandatory_checks
    return (
        checks.self_ban == "none"
        and checks.bureau == "free"
        and checks.biometry == "passed"
        and checks.phone_owner_match
    )


def test_world_models_release_and_scored_decision(node: Node) -> None:
    assessments = _replay_world(node, 0.02)
    base = load_training_config(node.ctx.env.scoring_config_path)
    # крошечный мир: одно широкое окно проверки, чтобы в нём были позитивы; правила разбиения — те же
    evaluation = base.evaluation.model_copy(update={"folds": 1, "test_span": 0.4})
    cfg = base.model_copy(update={"min_positives": 1, "min_calibration_positives": 1, "evaluation": evaluation})
    with node.ctx.db.transaction() as session:
        world = realms.resolve(session, node.world_id, node.clock.now())
        result = pipeline.run(session, world, cfg, node.ctx.policies.active.policy, node.ctx.index_key, START)
    assert result.versions, [
        {k: m.get(k) for k in ("model", "skipped", "positives", "folds")} for m in result.report["models"]
    ]
    summary = next(m for m in result.report["models"] if "skipped" not in m)
    assert {"rules_graph_baseline", "per_application", "with_graph"} <= summary["ablation"].keys()
    assert summary["family"] in ("lightgbm", "logistic") and "days" in summary["load"]

    realm = node.new_sandbox()
    risk1, risk2 = node.staff(realm, "risk-1"), node.staff(realm, "risk-2")
    model = result.versions[0]
    requested = node.client.post(f"/v1/models/{model.id}/releases", headers=risk1).json()
    same = node.client.post(f"/v1/models/releases/{requested['release_id']}/approval", headers=risk1)
    assert same.status_code == 403 and same.json()["error"]["code"] == "second_signer_required"
    approved = node.client.post(f"/v1/models/releases/{requested['release_id']}/approval", headers=risk2)
    assert approved.status_code == 200
    statuses = {m["model_version_id"]: m["status"] for m in node.client.get("/v1/models", headers=risk1).json()}
    assert statuses[str(model.id)] == "active"

    point = model.points[0]
    template = next(a for a in assessments if a.point == point and _passes_mandatory(a.snapshot)).snapshot.model_dump(
        mode="json"
    )
    template["applicant"]["pinfl"] = "31234567890123"
    decision = node.assess(realm, "LIVE-1", template, point=point)
    analyst = node.staff(realm, "analyst-1")
    record = node.client.get(f"/v1/decisions/{decision['decision_id']}", headers=analyst).json()["record"]
    assert record["inputs"]["scoring"]["status"] == "scored"
    assert str(model.id) in record["versions"]["models"]
    replay = node.client.get(f"/v1/decisions/{decision['decision_id']}/replay", headers=analyst).json()
    assert replay["identical"] is True
    compared = node.client.post(
        f"/v1/decisions/{decision['decision_id']}/comparison", headers=analyst, json={"policy_version": "policy-v1"}
    )
    assert compared.status_code == 200 and compared.json()["policy_version"] == "policy-v1"

    other = node.new_sandbox()
    elsewhere = node.assess(other, "LIVE-2", template, point=point)
    assert not any(r["code"].startswith("MODEL_") for r in elsewhere["reasons"]), "выпуск песочницы не виден другим"


def _inps(node: Node, realm: Any, pinfl: str, version: int, amount: int) -> None:
    months = [{"month": f"2025-{m:02d}", "amount": 100_000, "voluntary": False} for m in range(1, 13)]
    months += [{"month": f"2026-{m:02d}", "amount": amount, "voluntary": True} for m in range(1, 4)]
    node.event(
        realm,
        f"{pinfl}:app",
        version,
        type_="inps.contributions",
        entity_type="inps_contributions",
        payload={"subject_pinfl": pinfl, "months": months},
    )


def test_late_correction_is_invisible_to_earlier_assessment(node: Node) -> None:
    """Поздняя правка взносов не меняет прошлую оценку: признак считается по received_at ≤ as_of."""
    realm, pinfl = node.new_sandbox(), "31111111111111"
    _inps(node, realm, pinfl, 1, 400_000)
    snapshot = online(pinfl, "998901112233")
    decision = node.assess(realm, "A", snapshot)
    assessed_at = node.clock.now()
    node.clock.set(assessed_at + timedelta(days=5))
    _inps(node, realm, pinfl, 2, 100_000)

    def jump(as_of: Any) -> Any:
        with node.ctx.db.transaction() as session:
            context = realms.resolve(session, realm, node.clock.now())
            app_id = node.sql("select id from applications where external_id = 'A'")[0][0]
            policy = node.ctx.policies.active.policy
            vector = features.compute(
                session,
                context,
                app_id,
                "T1",
                ApplicationSnapshot.model_validate(snapshot),
                as_of,
                policy,
                node.ctx.index_key,
            ).vector
            return vector.values["income_jump_ratio"]

    stored = node.client.get(f"/v1/decisions/{decision['decision_id']}", headers=node.staff(realm, "analyst-1")).json()[
        "record"
    ]["inputs"]["features"]["values"]["income_jump_ratio"]
    assert stored == jump(assessed_at) == 4.0
    assert jump(node.clock.now()) == 1.0
