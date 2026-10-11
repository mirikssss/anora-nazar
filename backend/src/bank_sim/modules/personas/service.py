"""Роли имитатора и персоны заёмщиков: сиды из YAML, список для страницы входа и приложения заёмщика."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from bank_sim.modules.personas import repository
from bank_sim.modules.personas.domain import PersonaProfile, PersonaSeed
from bank_sim.modules.personas.models import BankRole, BorrowerPersona
from shared.config import load_yaml
from shared.errors import NotFoundError

BORROWERS_FILE = "borrower_personas.yaml"


@dataclass(frozen=True)
class Persona:
    code: str
    display_name: str
    birth_date: date
    summary: str
    profile: PersonaProfile


def load_borrowers(seeds_dir: Path) -> list[PersonaSeed]:
    return [PersonaSeed.model_validate(row) for row in load_yaml(seeds_dir / BORROWERS_FILE)["personas"]]


def seed(session: Session, seeds_dir: Path) -> None:
    for persona in load_borrowers(seeds_dir):
        repository.upsert_borrower(
            session,
            {
                "code": persona.code,
                "display_name": persona.display_name,
                "birth_date": persona.birth_date,
                "summary": persona.summary,
                "profile": persona.profile.model_dump(mode="json"),
            },
        )
    for role in load_yaml(seeds_dir / "roles.yaml")["roles"]:
        repository.upsert(
            session,
            {
                "code": role["code"],
                "title": role["title"],
                "home_path": role["home_path"],
                "summary": role["summary"],
                "permissions": role["permissions"],
                "restrictions": role.get("restrictions", []),
            },
        )


def roles(session: Session) -> list[BankRole]:
    return repository.all_roles(session)


def _persona(row: BorrowerPersona) -> Persona:
    return Persona(
        code=row.code,
        display_name=row.display_name,
        birth_date=row.birth_date,
        summary=row.summary,
        profile=PersonaProfile.model_validate(row.profile),
    )


def borrowers(session: Session) -> list[Persona]:
    return [_persona(row) for row in repository.borrowers(session)]


def borrower(session: Session, code: str) -> Persona:
    row = repository.borrower(session, code)
    if row is None:
        raise NotFoundError("persona_not_found", "Такой персоны нет")
    return _persona(row)
