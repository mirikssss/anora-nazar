"""Схемы выхода API модуля: тексты на одном языке, по аудитории."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class LabelOut(BaseModel):
    title: str
    description: str | None


class StaffReasonOut(BaseModel):
    title: str
    explanation: str
    client_template: str


class TransferActionOut(BaseModel):
    title: str
    description: str | None
    client_message: str


class VerificationQuestionOut(BaseModel):
    text: str
    answers: dict[str, str]


class ClientScreenOut(BaseModel):
    title: str
    body: str
    warning: str | None
    buttons: dict[str, str]


class _CatalogOut(BaseModel):
    version: str
    hash: str
    lang: str


class StaffTextsOut(_CatalogOut):
    """Сотруднику — всё: полные формулировки причин, названия признаков, подписи справочников."""

    audience: Literal["staff"]
    reasons: dict[str, StaffReasonOut]
    features: dict[str, LabelOut]
    levels: dict[str, LabelOut]
    reason_sources: dict[str, LabelOut]
    data_sources: dict[str, LabelOut]
    actions: dict[str, LabelOut]
    case_outcomes: dict[str, LabelOut]
    participant_actions: dict[str, LabelOut]
    participant_roles: dict[str, LabelOut]
    checklist_items: dict[str, LabelOut]
    benign_explanations: dict[str, LabelOut]
    queues: dict[str, LabelOut]
    case_statuses: dict[str, LabelOut]
    hold_statuses: dict[str, LabelOut]
    verification_questions: dict[str, VerificationQuestionOut]
    transfer_actions: dict[str, TransferActionOut]
    client_screens: dict[str, ClientScreenOut]


class ClientTextsOut(_CatalogOut):
    """Заёмщику — общая причина без названия признака: reasons — код → шаблон для клиента."""

    audience: Literal["client"]
    levels: dict[str, str]
    reasons: dict[str, str]
    verification_questions: dict[str, VerificationQuestionOut]
    client_screens: dict[str, ClientScreenOut]
    transfer_actions: dict[str, str]


TextsOut = Annotated[StaffTextsOut | ClientTextsOut, Field(discriminator="audience")]
