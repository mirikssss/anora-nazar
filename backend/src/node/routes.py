"""Сборка роутеров модулей узла."""

from fastapi import FastAPI

from node.modules.applications.api import router as applications
from node.modules.audit.api import router as audit
from node.modules.decisions.api import router as decisions
from node.modules.identity.api import router as identity
from node.modules.ingest.api import router as ingest
from node.modules.permits.api import router as permits
from node.modules.realms.api import router as realms
from node.modules.system.api import router as system


def include_routers(app: FastAPI) -> None:
    for router in (system, realms, identity, decisions, permits, ingest, applications, audit):
        app.include_router(router)
