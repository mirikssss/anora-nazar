"""Каталог текстов: модели, проверка языков и полноты. Без ввода-вывода.

Каждый текст — словарь по языкам ({ru: "..."}): узбекский добавляется данными, без правки кода.
"""

from collections.abc import Iterable, Iterator, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

Audience = Literal["staff", "client"]
CATALOG_META = frozenset({"version", "languages", "default_language"})
VERIFICATION_ANSWERS = "verification_answers"


class Localized(RootModel[dict[str, str]]):
    model_config = ConfigDict(frozen=True)

    def resolve(self, lang: str) -> str:
        return self.root[lang]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Label(_Frozen):
    title: Localized
    description: Localized | None = None


class ReasonText(_Frozen):
    staff_title: Localized
    staff_explanation: Localized
    client_template: Localized


class TransferActionText(Label):
    client_message: Localized


class VerificationQuestionText(_Frozen):
    text: Localized
    answers: dict[str, Localized] = Field(min_length=1)


class ClientScreenText(_Frozen):
    title: Localized
    body: Localized
    warning: Localized | None = None
    buttons: dict[str, Localized] = Field(min_length=1)


class TextCatalog(_Frozen):
    version: str
    languages: list[str] = Field(min_length=1)
    default_language: str
    reasons: dict[str, ReasonText]
    features: dict[str, Label]
    levels: dict[str, Label]
    reason_sources: dict[str, Label]
    data_sources: dict[str, Label]
    actions: dict[str, Label]
    case_outcomes: dict[str, Label]
    participant_actions: dict[str, Label]
    participant_roles: dict[str, Label]
    checklist_items: dict[str, Label]
    benign_explanations: dict[str, Label]
    queues: dict[str, Label]
    case_statuses: dict[str, Label]
    hold_statuses: dict[str, Label]
    verification_questions: dict[str, VerificationQuestionText]
    transfer_actions: dict[str, TransferActionText]
    client_screens: dict[str, ClientScreenText]

    @model_validator(mode="after")
    def _every_text_in_every_language(self) -> "TextCatalog":
        if self.default_language not in self.languages:
            raise ValueError(f"Язык по умолчанию {self.default_language} не входит в {self.languages}")
        expected = set(self.languages)
        broken = [
            path
            for path, text in _localized(self, "")
            if set(text.root) != expected or not all(value.strip() for value in text.root.values())
        ]
        if broken:
            raise ValueError(f"Тексты пустые или не на языках {sorted(expected)}: {broken}")
        return self

    def codes(self) -> dict[str, set[str]]:
        """Раздел → коды с текстом; ответы проверки намерения — как «вопрос.ответ»."""
        sections = {name: set(getattr(self, name)) for name in TextCatalog.model_fields if name not in CATALOG_META}
        sections[VERIFICATION_ANSWERS] = {
            f"{question_code}.{answer_code}"
            for question_code, question in self.verification_questions.items()
            for answer_code in question.answers
        }
        return sections


def _localized(value: object, path: str) -> Iterator[tuple[str, Localized]]:
    if isinstance(value, Localized):
        yield path, value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _localized(getattr(value, name), _join(path, name))
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _localized(item, _join(path, key))


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def missing_texts(catalog: TextCatalog, required: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
    """Коды из источников без текста: раздел → отсортированные коды. Пустой словарь — каталог полон."""
    present = catalog.codes()
    unknown = required.keys() - present.keys()
    if unknown:
        raise ValueError(f"В каталоге нет разделов {sorted(unknown)}")
    missing = {section: sorted(set(codes) - present[section]) for section, codes in required.items()}
    return {section: codes for section, codes in missing.items() if codes}
