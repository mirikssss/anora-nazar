"""Сборка роутеров модулей имитатора."""

from fastapi import FastAPI

from bank_sim.modules.borrower_app.api import router as borrower_app
from bank_sim.modules.conveyor.api import router as conveyor
from bank_sim.modules.core_banking.api import router as core_banking
from bank_sim.modules.failures.api import router as failures
from bank_sim.modules.incidents.api import router as incidents
from bank_sim.modules.notifications.api import router as notifications
from bank_sim.modules.personas.api import router as personas
from bank_sim.modules.program_platform.api import router as program_platform
from bank_sim.modules.sandboxes.api import router as sandboxes
from bank_sim.modules.scenarios.api import router as scenarios
from bank_sim.modules.sessions.api import router as sessions
from bank_sim.modules.sources.api import router as sources
from bank_sim.modules.staff.api import router as staff
from bank_sim.modules.system.api import router as system
from bank_sim.modules.transfers.api import router as transfers


def include_routers(app: FastAPI) -> None:
    for router in (
        system,
        sandboxes,
        personas,
        staff,
        sources,
        sessions,
        conveyor,
        core_banking,
        failures,
        notifications,
        borrower_app,
        program_platform,
        transfers,
        incidents,
        scenarios,
    ):
        app.include_router(router)
