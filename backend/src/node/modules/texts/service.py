"""Каталог текстов: загрузка из YAML с версией и хешем, выдача по аудитории и языку."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from pydantic import ValidationError

from node.modules.texts.domain import (
    Audience,
    ClientScreenText,
    Label,
    Localized,
    TextCatalog,
    VerificationQuestionText,
)
from node.modules.texts.schemas import (
    ClientScreenOut,
    ClientTextsOut,
    LabelOut,
    StaffReasonOut,
    StaffTextsOut,
    TransferActionOut,
    VerificationQuestionOut,
)
from shared.config import load_yaml
from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConfigurationError, ValidationFailedError

CATALOG_DIR = Path(__file__).parent / "catalog"


@dataclass(frozen=True)
class LoadedCatalog:
    catalog: TextCatalog
    hash: str


def load_catalog(path: Path) -> LoadedCatalog:
    raw = load_yaml(path)
    try:
        catalog = TextCatalog.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"{path.name}: {exc}") from exc
    return LoadedCatalog(catalog=catalog, hash=sha256_hex(raw))


@cache
def catalog(version: str) -> LoadedCatalog:
    """Каталог по версии из конфигурации узла (texts.active_catalog); правка текстов — новый файл и новая версия."""
    return load_catalog(CATALOG_DIR / f"{version}.yaml")


def texts(version: str, audience: Audience, lang: str | None) -> StaffTextsOut | ClientTextsOut:
    return render(catalog(version), audience, lang)


def render(loaded: LoadedCatalog, audience: Audience, lang: str | None) -> StaffTextsOut | ClientTextsOut:
    catalog = loaded.catalog
    language = lang or catalog.default_language
    if language not in catalog.languages:
        raise ValidationFailedError(
            "unsupported_language", f"Тексты на языке «{language}» не готовы", {"languages": catalog.languages}
        )
    if audience == "client":
        return _client(loaded, language)
    return _staff(loaded, language)


def _staff(loaded: LoadedCatalog, lang: str) -> StaffTextsOut:
    c = loaded.catalog
    return StaffTextsOut(
        audience="staff",
        version=c.version,
        hash=loaded.hash,
        lang=lang,
        reasons={
            code: StaffReasonOut(
                title=r.staff_title.resolve(lang),
                explanation=r.staff_explanation.resolve(lang),
                client_template=r.client_template.resolve(lang),
            )
            for code, r in c.reasons.items()
        },
        features=_labels(c.features, lang),
        levels=_labels(c.levels, lang),
        reason_sources=_labels(c.reason_sources, lang),
        data_sources=_labels(c.data_sources, lang),
        actions=_labels(c.actions, lang),
        case_outcomes=_labels(c.case_outcomes, lang),
        participant_actions=_labels(c.participant_actions, lang),
        participant_roles=_labels(c.participant_roles, lang),
        checklist_items=_labels(c.checklist_items, lang),
        benign_explanations=_labels(c.benign_explanations, lang),
        queues=_labels(c.queues, lang),
        case_statuses=_labels(c.case_statuses, lang),
        hold_statuses=_labels(c.hold_statuses, lang),
        verification_questions=_questions(c.verification_questions, lang),
        transfer_actions={
            code: TransferActionOut(
                title=a.title.resolve(lang),
                description=_optional(a.description, lang),
                client_message=a.client_message.resolve(lang),
            )
            for code, a in c.transfer_actions.items()
        },
        client_screens=_screens(c.client_screens, lang),
    )


def _client(loaded: LoadedCatalog, lang: str) -> ClientTextsOut:
    """Без формулировок для сотрудника и без названий признаков: заёмщик не должен узнать, что сработало."""
    c = loaded.catalog
    return ClientTextsOut(
        audience="client",
        version=c.version,
        hash=loaded.hash,
        lang=lang,
        levels={code: level.title.resolve(lang) for code, level in c.levels.items()},
        reasons={code: r.client_template.resolve(lang) for code, r in c.reasons.items()},
        verification_questions=_questions(c.verification_questions, lang),
        client_screens=_screens(c.client_screens, lang),
        transfer_actions={code: a.client_message.resolve(lang) for code, a in c.transfer_actions.items()},
    )


def _optional(text: Localized | None, lang: str) -> str | None:
    return text.resolve(lang) if text is not None else None


def _resolved(texts: Mapping[str, Localized], lang: str) -> dict[str, str]:
    return {code: text.resolve(lang) for code, text in texts.items()}


def _labels(section: Mapping[str, Label], lang: str) -> dict[str, LabelOut]:
    return {
        code: LabelOut(title=label.title.resolve(lang), description=_optional(label.description, lang))
        for code, label in section.items()
    }


def _questions(section: Mapping[str, VerificationQuestionText], lang: str) -> dict[str, VerificationQuestionOut]:
    return {
        code: VerificationQuestionOut(text=q.text.resolve(lang), answers=_resolved(q.answers, lang))
        for code, q in section.items()
    }


def _screens(section: Mapping[str, ClientScreenText], lang: str) -> dict[str, ClientScreenOut]:
    return {
        code: ClientScreenOut(
            title=s.title.resolve(lang),
            body=s.body.resolve(lang),
            warning=_optional(s.warning, lang),
            buttons=_resolved(s.buttons, lang),
        )
        for code, s in section.items()
    }
