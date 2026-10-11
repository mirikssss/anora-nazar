"""Сборка роутеров модулей оператора."""

from fastapi import FastAPI

from network_operator.modules.activity.api import router as activity
from network_operator.modules.confirmed.api import router as confirmed
from network_operator.modules.counters.api import router as counters
from network_operator.modules.oprf.api import router as oprf
from network_operator.modules.realms.api import router as realms
from network_operator.modules.stats.api import router as stats
from network_operator.modules.system.api import router as system


def include_routers(app: FastAPI) -> None:
    for router in (system, oprf, activity, counters, confirmed, stats, realms):
        app.include_router(router)
