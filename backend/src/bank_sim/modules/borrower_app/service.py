"""Приложение заёмщика: онлайн-заявка через конвейер, экран по решению узла, ответы на проверку намерения,
сигнал «Меня просят взять кредит» и отмена клиентом. Снять паузу из приложения нельзя (Блок 4)."""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from bank_sim.context import BankContext
from bank_sim.modules.borrower_app import domain, repository
from bank_sim.modules.borrower_app.domain import BorrowerState, Notice, Screen
from bank_sim.modules.borrower_app.models import BorrowerApplication
from bank_sim.modules.borrower_app.schemas import (
    BorrowerApplicationIn,
    BorrowerScreenOut,
    IntentAnswersIn,
    LoanOut,
    PersonaOut,
    Questions,
)
from bank_sim.modules.cards import service as cards
from bank_sim.modules.conveyor import service as conveyor
from bank_sim.modules.conveyor.models import ConveyorApplication
from bank_sim.modules.conveyor.schemas import ApplicationDraft, SimulatedChecks
from bank_sim.modules.failures import service as failures
from bank_sim.modules.notifications import service as notifications
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.personas import service as personas
from bank_sim.modules.personas.domain import age
from bank_sim.modules.sessions import service as sessions
from bank_sim.modules.sources import service as sources
from shared.contracts.application import Loan
from shared.contracts.facts import IntentAnswers, PressureReported
from shared.errors import AppError, ConflictError, NotFoundError, UpstreamUnavailableError, ValidationFailedError

log = logging.getLogger(__name__)

SOURCE = "bank-sim.borrower-app"
APPLICATION_ENTITY = "application"
INTENT_EVENT = "client.intent_answers"
PRESSURE_EVENT = "client.pressure_reported"
INTENT_SCREEN: Screen = "intent_check"
CLOSED_SCREENS: set[Screen] = {"cancelled", "stopped"}


@dataclass(frozen=True)
class _Loaded:
    record: BorrowerApplication
    app: ConveyorApplication
    state: BorrowerState
    credited: bool

    @property
    def pinfl(self) -> str:
        return str(self.app.snapshot["applicant"]["pinfl"])


def personas_view(ctx: BankContext) -> list[PersonaOut]:
    today = ctx.clock.now().date()
    with ctx.db.transaction() as session:
        found = personas.borrowers(session)
    return [
        PersonaOut(
            code=p.code,
            display_name=p.display_name,
            age=age(p.birth_date, today),
            summary=p.summary,
            pinfl=p.profile.applicant.pinfl,
            phone=p.profile.applicant.phone,
            address=p.profile.applicant.address,
            registration_mahalla=p.profile.applicant.registration_mahalla,
            card_balance=p.profile.card_balance,
        )
        for p in found
    ]


def register(session: Session, realm_id: UUID, application_id: str, persona_code: str | None, now: datetime) -> None:
    """Заявка видна в приложении заёмщика: подана персоной или сценарием онлайн-канала."""
    repository.add(
        session,
        BorrowerApplication(
            realm_id=realm_id,
            application_id=application_id,
            persona_code=persona_code,
            intent_answers=None,
            intent_answered_at=None,
            pressure_reported_at=None,
            created_at=now,
        ),
    )


def _check_terms(ctx: BankContext, body: BorrowerApplicationIn) -> None:
    limits = ctx.config.borrower
    if not limits.amount.min <= body.amount <= limits.amount.max:
        raise ValidationFailedError(
            "amount_out_of_range",
            f"Сумма онлайн-займа — от {limits.amount.min} до {limits.amount.max} сум",
            {"min": limits.amount.min, "max": limits.amount.max},
        )
    if body.term_months not in limits.terms_months:
        raise ValidationFailedError(
            "term_not_offered", "Такого срока нет в предложении банка", {"terms_months": limits.terms_months}
        )


def create(ctx: BankContext, realm_id: UUID, body: BorrowerApplicationIn) -> BorrowerScreenOut:
    """Заявка персоны: обязательные шаги конвейера, ответы источников и сводка сессии — в узел, затем Т1."""
    _check_terms(ctx, body)
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        persona = personas.borrower(session, body.persona_code)
        profile = persona.profile
        applicant = profile.applicant
        draft = ApplicationDraft(
            channel="online",
            branch_id=ctx.config.borrower.branch_id,
            applicant=applicant,
            loan=Loan(amount=body.amount, term_months=body.term_months),
            disbursement_account=profile.account,
            checks=SimulatedChecks(biometry=profile.biometry, phone_owner_match=profile.phone_owner_match),
        )
        application_id = conveyor.create(session, realm_id, draft, now).external_id
        register(session, realm_id, application_id, persona.code, now)
        cards.open_account(session, realm_id, applicant.pinfl, profile.account, profile.card_balance, now)
        cards.remember_recipients(session, realm_id, applicant.pinfl, profile.known_recipients, now)
        sources.report_profile(session, realm_id, applicant.pinfl, profile.sources, now)
        if profile.session is not None and applicant.device_id is not None:
            sessions.report_summary(
                session,
                realm_id,
                pinfl=applicant.pinfl,
                application_id=application_id,
                device_id=applicant.device_id,
                profile=profile.session,
                now=now,
            )
    submit(ctx, realm_id, application_id)
    return view(ctx, realm_id, application_id)


def submit(ctx: BankContext, realm_id: UUID, application_id: str) -> None:
    """Т1 после того, как факты источников дошли до узла. Узел недоступен — заявка ждёт («на проверке»)."""
    outbox.flush_realm(ctx, realm_id)
    try:
        conveyor.assess(ctx, realm_id, application_id)
    except UpstreamUnavailableError as exc:
        log.info("заявка %s ждёт узел: %s", application_id, exc.message)


def _load(session: Session, realm_id: UUID, application_id: str, *, lock: bool = False) -> _Loaded:
    record = repository.get(session, realm_id, application_id, lock=lock)
    if record is None:
        raise NotFoundError("borrower_application_not_found", "В приложении заёмщика такой заявки нет")
    app = conveyor.get(session, realm_id, application_id)
    notices = tuple(
        Notice(topic=n.topic, payload=n.payload, received_at=n.received_at)
        for n in notifications.for_application(session, realm_id, application_id)
    )
    state = BorrowerState(
        status=app.status,
        decision=app.last_decision,
        notices=notices,
        intent_answered=record.intent_answered_at is not None,
        pressure_reported_at=record.pressure_reported_at,
    )
    return _Loaded(record, app, state, cards.credit_for(session, realm_id, application_id) is not None)


def _questions(ctx: BankContext, realm_id: UUID) -> Questions | None:
    """Вопросы проверки намерения из узла; недоступны — экран скажет об этом, а не покажет пустую форму."""
    with ctx.db.transaction() as session:
        flags = failures.flags(session, realm_id)
    try:
        failures.ensure_node_reachable(flags)
        return Questions.model_validate(ctx.node.verification_questions())
    except AppError as exc:
        log.warning("вопросы проверки намерения недоступны: %s", exc.message)
    except ValidationError as exc:
        log.warning("узел вернул вопросы проверки намерения не по контракту: %s", exc)
    return None


def _out(ctx: BankContext, loaded: _Loaded, *, with_questions: bool) -> BorrowerScreenOut:
    screen = domain.screen(loaded.state, ctx.config.borrower.screens)
    asked = with_questions and screen == INTENT_SCREEN
    questions = _questions(ctx, loaded.record.realm_id) if asked else None
    loan = loaded.app.snapshot["loan"]
    return BorrowerScreenOut(
        application_id=loaded.app.external_id,
        persona_code=loaded.record.persona_code,
        status=loaded.app.status,
        screen=screen,
        reason_codes=[] if screen == "approved" else domain.reason_codes(loaded.state.decision),
        questions=questions,
        questions_unavailable=asked and questions is None,
        intent_answered=loaded.state.intent_answered,
        pressure_reported=loaded.state.pressure_reported_at is not None,
        can_cancel=screen not in CLOSED_SCREENS and not loaded.credited,
        loan=LoanOut(amount=int(loan["amount"]), term_months=int(loan["term_months"])),
        created_at=loaded.record.created_at,
        updated_at=loaded.app.updated_at,
    )


def view(ctx: BankContext, realm_id: UUID, application_id: str) -> BorrowerScreenOut:
    with ctx.db.transaction() as session:
        loaded = _load(session, realm_id, application_id)
    return _out(ctx, loaded, with_questions=True)


def list_views(ctx: BankContext, realm_id: UUID, persona_code: str | None) -> list[BorrowerScreenOut]:
    with ctx.db.transaction() as session:
        loaded = [
            _load(session, realm_id, r.application_id)
            for r in repository.list_for_realm(session, realm_id, persona_code)
        ]
    return [_out(ctx, item, with_questions=False) for item in loaded]


def _emit(session: Session, realm_id: UUID, type_: str, application_id: str, payload: BaseModel, now: datetime) -> None:
    outbox.emit(
        session,
        realm_id,
        source=SOURCE,
        type_=type_,
        entity_type=APPLICATION_ENTITY,
        entity_id=application_id,
        entity_version=None,
        payload=payload.model_dump(mode="json"),
        occurred_at=now,
    )


def answer_intent(ctx: BankContext, realm_id: UUID, application_id: str, body: IntentAnswersIn) -> BorrowerScreenOut:
    """Ответы кнопками на проверку намерения — событием в узел; решает узел, приложение ждёт его ответа."""
    current = view(ctx, realm_id, application_id)
    if current.intent_answered:
        raise ConflictError("intent_already_answered", "Ответы на проверку намерения уже отправлены")
    if current.screen != INTENT_SCREEN:
        raise ConflictError("intent_check_not_required", "Проверка намерения по этой заявке сейчас не нужна")
    if current.questions is not None:
        options = {q.code: {a.code for a in q.answers} for q in current.questions.questions}
        try:
            domain.check_answers(options, [(a.question, a.answer) for a in body.answers])
        except ValueError as exc:
            raise ValidationFailedError("invalid_answers", str(exc)) from exc
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        loaded = _load(session, realm_id, application_id, lock=True)
        if loaded.record.intent_answered_at is not None:
            raise ConflictError("intent_already_answered", "Ответы на проверку намерения уже отправлены")
        loaded.record.intent_answers = [a.model_dump() for a in body.answers]
        loaded.record.intent_answered_at = now
        payload = IntentAnswers(subject_pinfl=loaded.pinfl, application_id=application_id, answers=body.answers)
        _emit(session, realm_id, INTENT_EVENT, application_id, payload, now)
    outbox.flush_realm(ctx, realm_id)
    return view(ctx, realm_id, application_id)


def report_pressure(ctx: BankContext, realm_id: UUID, application_id: str) -> BorrowerScreenOut:
    """«Меня просят взять кредит»: сигнал уходит молча, без вопроса «вы уверены?»; повторное нажатие не дублирует."""
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        loaded = _load(session, realm_id, application_id, lock=True)
        if loaded.app.status == "cancelled":
            raise ConflictError("application_cancelled", "Заявка отменена")
        if loaded.record.pressure_reported_at is None:
            loaded.record.pressure_reported_at = now
            payload = PressureReported(subject_pinfl=loaded.pinfl, application_id=application_id)
            _emit(session, realm_id, PRESSURE_EVENT, application_id, payload, now)
    outbox.flush_realm(ctx, realm_id)
    return view(ctx, realm_id, application_id)


def cancel(ctx: BankContext, realm_id: UUID, application_id: str) -> BorrowerScreenOut:
    """Клиент отменяет заявку через конвейер; после зачисления отменять нечего."""
    with ctx.db.transaction() as session:
        loaded = _load(session, realm_id, application_id, lock=True)
        if loaded.credited:
            raise ConflictError("credit_already_disbursed", "Кредит уже зачислен — отменить заявку нельзя")
        conveyor.cancel(session, realm_id, application_id, ctx.clock.now())
    outbox.flush_realm(ctx, realm_id)
    return view(ctx, realm_id, application_id)
