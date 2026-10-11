"""Филиалы и сотрудники: сид и проверка, что сотрудник из этого филиала."""

from pathlib import Path

from sqlalchemy.orm import Session

from bank_sim.modules.staff import repository
from bank_sim.modules.staff.models import Branch, Employee
from shared.config import load_yaml
from shared.errors import ValidationFailedError


def seed(session: Session, seeds_dir: Path) -> None:
    data = load_yaml(seeds_dir / "branches.yaml")
    for row in data["branches"]:
        repository.upsert(session, Branch, row)
    for row in data["employees"]:
        repository.upsert(session, Employee, row)


def upsert_world(session: Session, branches: list[dict[str, str]], employees: list[dict[str, str]]) -> None:
    """Филиалы и сотрудники синтетического мира — тот же персонал, что в истории узла."""
    for row in branches:
        repository.upsert(session, Branch, row)
    for row in employees:
        repository.upsert(session, Employee, row)


def branches(session: Session) -> list[tuple[Branch, list[Employee]]]:
    employees = repository.employees(session)
    return [(b, [e for e in employees if e.branch_id == b.id]) for b in repository.branches(session)]


def ensure_assignment(session: Session, branch_id: str, employee_id: str | None) -> None:
    if repository.branch(session, branch_id) is None:
        raise ValidationFailedError("unknown_branch", "Такого филиала нет")
    if employee_id is None:
        return
    employee = repository.employee(session, employee_id)
    if employee is None or employee.branch_id != branch_id:
        raise ValidationFailedError("unknown_employee", "Этот сотрудник не работает в выбранном филиале")
