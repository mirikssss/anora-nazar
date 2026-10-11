"""Роли имитатора: сид из YAML и список для страницы входа."""

from pathlib import Path

from sqlalchemy.orm import Session

from bank_sim.modules.personas import repository
from bank_sim.modules.personas.models import BankRole
from shared.config import load_yaml


def seed(session: Session, seeds_dir: Path) -> None:
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
