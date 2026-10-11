"""Роутер модуля: каталог сценариев трёх зон, запуск в песочнице посетителя, запуски песочницы."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.scenarios import service
from bank_sim.modules.scenarios.models import ScenarioRun
from bank_sim.modules.scenarios.schemas import ExpectedOut, RunApplicationOut, ScenarioOut, ScenarioRunOut

router = APIRouter(prefix="/v1/scenarios", tags=["Сценарии"])


def _run(record: ScenarioRun) -> ScenarioRunOut:
    return ScenarioRunOut(
        run_id=record.id,
        number=record.number,
        scenario_code=record.scenario_code,
        applications=[RunApplicationOut.model_validate(a) for a in record.applications],
        created_at=record.created_at,
        finished_at=record.finished_at,
    )


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(ctx: Ctx) -> list[ScenarioOut]:
    return [
        ScenarioOut(
            code=s.code,
            zone=s.zone,
            title=s.title,
            summary=s.summary,
            expected=ExpectedOut(level=s.expected.level, action=s.expected.action),
            expected_summary=s.expected_summary,
            applications=service.applications_count(s),
        )
        for s in service.book(ctx).scenarios
    ]


@router.post("/{code}/runs", response_model=ScenarioRunOut, status_code=201)
def run(code: str, ctx: Ctx, realm: Realm) -> ScenarioRunOut:
    """Выполняет шаги сценария в песочнице; участники каждого запуска новые."""
    return _run(service.run(ctx, realm, code))


@router.get("/runs", response_model=list[ScenarioRunOut])
def list_runs(ctx: Ctx, realm: Realm) -> list[ScenarioRunOut]:
    return [_run(r) for r in service.runs(ctx, realm)]
