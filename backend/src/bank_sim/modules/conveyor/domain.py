"""Чистая логика конвейера: сборка снимка и применение изменения условий."""

from typing import Any, Literal

from bank_sim.modules.conveyor.schemas import ApplicationChange, ApplicationDraft
from shared.contracts.application import ApplicationSnapshot, MandatoryChecks


def build_snapshot(
    draft: ApplicationDraft, self_ban: Literal["active", "none"], bureau: Literal["free", "blocked", "busy"]
) -> ApplicationSnapshot:
    """Снимок для узла: заявка + итоги обязательных шагов № 3759, выполненных конвейером до вызова узла."""
    return ApplicationSnapshot(
        channel=draft.channel,
        branch_id=draft.branch_id,
        employee_id=draft.employee_id,
        applicant=draft.applicant,
        loan=draft.loan,
        disbursement_account=draft.disbursement_account,
        program=draft.program,
        session_refs=draft.session_refs,
        mandatory_checks=MandatoryChecks(
            self_ban=self_ban,
            bureau=bureau,
            biometry=draft.checks.biometry,
            phone_owner_match=draft.checks.phone_owner_match,
        ),
    )


def apply_change(draft: dict[str, Any], change: ApplicationChange) -> ApplicationDraft:
    updated = dict(draft)
    updated["loan"] = {**draft["loan"], **change.model_dump(include={"amount", "term_months"}, exclude_none=True)}
    if change.disbursement_account is not None:
        updated["disbursement_account"] = change.disbursement_account
    program_change = {
        key: value
        for key, value in (
            ("supplier_account", change.supplier_account),
            ("unit_price", change.unit_price),
            ("quantity", change.quantity),
        )
        if value is not None
    }
    if program_change:
        if draft.get("program") is None:
            raise ValueError("У онлайн-заявки нет программной части")
        updated["program"] = {**draft["program"], **program_change}
    return ApplicationDraft.model_validate(updated)
