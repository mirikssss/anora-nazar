"""Сборка роутеров модулей имитатора."""

from fastapi import FastAPI

from bank_sim.modules.conveyor.api import router as conveyor
from bank_sim.modules.core_banking.api import router as core_banking
from bank_sim.modules.failures.api import router as failures
from bank_sim.modules.notifications.api import router as notifications
from bank_sim.modules.personas.api import router as personas
from bank_sim.modules.sandboxes.api import router as sandboxes
from bank_sim.modules.sessions.api import router as sessions
from bank_sim.modules.sources.api import router as sources
from bank_sim.modules.staff.api import router as staff
from bank_sim.modules.system.api import router as system


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
    ):
        app.include_router(router)
