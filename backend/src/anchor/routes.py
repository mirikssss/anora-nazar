"""Сборка роутеров модулей якоря."""

from fastapi import FastAPI

from anchor.modules.checkpoints.api import router as checkpoints
from anchor.modules.system.api import router as system


def include_routers(app: FastAPI) -> None:
    app.include_router(system)
    app.include_router(checkpoints)
