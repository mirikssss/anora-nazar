"""Роутер модуля: филиалы и сотрудники для формы заявки."""

from fastapi import APIRouter

from bank_sim.deps import Ctx
from bank_sim.modules.staff import service
from bank_sim.modules.staff.schemas import BranchOut, EmployeeOut

router = APIRouter(prefix="/v1/staff", tags=["Филиалы"])


@router.get("/branches", response_model=list[BranchOut])
def list_branches(ctx: Ctx) -> list[BranchOut]:
    with ctx.db.transaction() as session:
        return [
            BranchOut(
                id=b.id,
                name=b.name,
                district=b.district,
                employees=[EmployeeOut(id=e.id, display_name=e.display_name, role=e.role) for e in es],
            )
            for b, es in service.branches(session)
        ]
