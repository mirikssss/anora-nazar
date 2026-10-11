"""Сценарии трёх зон в один клик: шаги банка в песочнице посетителя — факты источников событиями в узел и заявки
через конвейер. Участники каждого запуска новые; итог — созданные заявки и решения узла по ним."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from random import Random
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bank_sim.context import BankContext
from bank_sim.modules.borrower_app import service as borrower
from bank_sim.modules.conveyor import service as conveyor
from bank_sim.modules.conveyor.schemas import ApplicationDraft
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.program_platform import service as program
from bank_sim.modules.scenarios import domain, repository
from bank_sim.modules.scenarios.domain import (
    ApplicationStep,
    BranchRef,
    Cast,
    CompanyStep,
    FactsStep,
    HelperRef,
    ItemRef,
    ScenarioBook,
    ScenarioError,
    ScenarioSpec,
    WorldRefs,
)
from bank_sim.modules.scenarios.models import ScenarioRun
from bank_sim.modules.scenarios.schemas import RunApplicationOut
from bank_sim.modules.sessions import service as sessions
from bank_sim.modules.sources import service as sources
from bank_sim.modules.staff import service as staff
from shared.config import load_yaml
from shared.errors import AppError, ConflictError, NotFoundError
from world.config import WorldParams, load_params

DEFINITIONS_FILE = "scenarios.yaml"
Draft = tuple[str, dict[str, Any]]


@dataclass(frozen=True)
class _Created:
    person: str
    channel: str
    application_id: str | None
    in_borrower_app: bool
    error: dict[str, Any] | None


@cache
def _book(path: Path) -> ScenarioBook:
    return ScenarioBook.model_validate(load_yaml(path))


@cache
def _world_params(path: Path) -> WorldParams:
    return load_params(path)


def book(ctx: BankContext) -> ScenarioBook:
    return _book(ctx.env.seeds_dir / DEFINITIONS_FILE)


def _refs(session: Session, ctx: BankContext) -> WorldRefs:
    params = _world_params(ctx.config.world_params_path)
    return WorldRefs(
        helpers=tuple(HelperRef(h.id, h.district, h.mahalla) for h in program.helpers(session)),
        branches=tuple(BranchRef(b.id, b.district, team[0].id) for b, team in staff.branches(session) if team),
        online_branch=ctx.config.borrower.branch_id,
        catalog={item.code: ItemRef(item.unit, item.median) for item in params.organizations.items},
        address_format=params.naming.address,
        operator_codes=tuple(params.population.phone_operator_codes),
        pinfl_district_codes=ctx.config.scenarios.pinfl_district_codes,
        house_numbers=ctx.config.scenarios.house_numbers,
    )


def _plan(spec: ScenarioSpec, refs: WorldRefs, rng: Random) -> tuple[Cast, list[list[Draft]]]:
    """Участники и черновики всех заявок — до первого шага: сценарий либо выполним целиком, либо не начинается."""
    crew = domain.cast(spec, refs, rng)
    drafts = [domain.application_drafts(s, crew, refs) if isinstance(s, ApplicationStep) else [] for s in spec.steps]
    return crew, drafts


def _start(ctx: BankContext, realm_id: UUID, spec: ScenarioSpec) -> tuple[UUID, int, Cast, list[list[Draft]]]:
    run_id = uuid4()
    try:
        with ctx.db.transaction() as session:
            number = repository.next_number(session, realm_id)
            crew, drafts = _plan(spec, _refs(session, ctx), Random(domain.run_seed(realm_id, number)))
            repository.add(
                session,
                ScenarioRun(
                    id=run_id,
                    realm_id=realm_id,
                    number=number,
                    scenario_code=spec.code,
                    applications=[],
                    created_at=ctx.clock.now(),
                    finished_at=None,
                ),
            )
    except ScenarioError as exc:
        raise ConflictError("scenario_not_runnable", str(exc)) from exc
    except IntegrityError as exc:
        raise ConflictError(
            "scenario_run_in_progress", "В этой песочнице уже запускается сценарий — повторите"
        ) from exc
    return run_id, number, crew, drafts


def _assess(ctx: BankContext, realm_id: UUID, application_id: str) -> dict[str, Any] | None:
    """Оценка после того, как факты дошли до узла; ошибка узла остаётся в итоге запуска, а не роняет его."""
    outbox.flush_realm(ctx, realm_id)
    try:
        conveyor.assess(ctx, realm_id, application_id)
    except AppError as exc:
        return {"code": exc.code, "message": exc.message}
    return None


def _apply(ctx: BankContext, realm_id: UUID, step: ApplicationStep, ref: str, raw: dict[str, Any]) -> _Created:
    online_app = step.branch == "online"
    now = ctx.clock.now()
    try:
        draft = ApplicationDraft.model_validate(raw)
    except ValidationError as exc:
        error = {
            "code": "invalid_draft",
            "message": "Черновик заявки не прошёл проверку",
            "details": exc.errors(include_url=False, include_context=False),
        }
        return _Created(ref, step.channel, None, False, error)
    with ctx.db.transaction() as session:
        application_id = conveyor.create(session, realm_id, draft, now).external_id
        device_id = draft.applicant.device_id
        if step.session is not None and device_id is not None:
            sessions.report_summary(
                session,
                realm_id,
                pinfl=draft.applicant.pinfl,
                application_id=application_id,
                device_id=device_id,
                profile=step.session,
                now=now,
            )
        if online_app:
            borrower.register(session, realm_id, application_id, None, now)
    return _Created(ref, step.channel, application_id, online_app, _assess(ctx, realm_id, application_id))


def _execute(
    ctx: BankContext, realm_id: UUID, spec: ScenarioSpec, crew: Cast, drafts: list[list[Draft]]
) -> list[_Created]:
    created: list[_Created] = []
    for step, step_drafts in zip(spec.steps, drafts, strict=True):
        if isinstance(step, FactsStep):
            with ctx.db.transaction() as session:
                for ref in step.people:
                    sources.report_profile(session, realm_id, crew.people[ref].pinfl, step.profile, ctx.clock.now())
        elif isinstance(step, CompanyStep):
            with ctx.db.transaction() as session:
                for ref in step.companies:
                    profile = spec.companies[ref].profile
                    sources.report_company(session, realm_id, crew.companies[ref].inn, profile, ctx.clock.now())
        else:
            created += [_apply(ctx, realm_id, step, ref, raw) for ref, raw in step_drafts]
    return created


def _result(session: Session, realm_id: UUID, item: _Created) -> RunApplicationOut:
    app = None if item.application_id is None else conveyor.get(session, realm_id, item.application_id)
    decision = None if app is None else app.last_decision
    return RunApplicationOut(
        person=item.person,
        application_id=item.application_id,
        channel=item.channel,
        status=None if app is None else app.status,
        node_state=None if app is None else app.node_state,
        level=None if decision is None else decision.get("level"),
        action=None if decision is None else decision.get("action"),
        last_decision=decision,
        in_borrower_app=item.in_borrower_app,
        error=item.error,
    )


def run(ctx: BankContext, realm_id: UUID, code: str) -> ScenarioRun:
    spec = book(ctx).find(code)
    if spec is None:
        raise NotFoundError("scenario_not_found", "Такого сценария нет")
    run_id, _, crew, drafts = _start(ctx, realm_id, spec)
    created = _execute(ctx, realm_id, spec, crew, drafts)
    with ctx.db.transaction() as session:
        record = repository.get(session, realm_id, run_id, lock=True)
        if record is None:
            raise NotFoundError("scenario_run_not_found", "Песочница удалена во время запуска")
        record.applications = [_result(session, realm_id, item).model_dump(mode="json") for item in created]
        record.finished_at = ctx.clock.now()
        return record


def runs(ctx: BankContext, realm_id: UUID) -> list[ScenarioRun]:
    with ctx.db.transaction() as session:
        return repository.list_for_realm(session, realm_id)


def applications_count(spec: ScenarioSpec) -> int:
    return sum(len(step.people) for step in spec.steps if isinstance(step, ApplicationStep))
