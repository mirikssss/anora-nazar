"""Все таблицы имитатора банка — для миграций."""

from bank_sim.database import Base
from bank_sim.modules.borrower_app import models as borrower_app
from bank_sim.modules.cards import models as cards
from bank_sim.modules.conveyor import models as conveyor
from bank_sim.modules.core_banking import models as core_banking
from bank_sim.modules.failures import models as failures
from bank_sim.modules.incidents import models as incidents
from bank_sim.modules.notifications import models as notifications
from bank_sim.modules.outbox import models as outbox
from bank_sim.modules.personas import models as personas
from bank_sim.modules.program_platform import models as program_platform
from bank_sim.modules.sandboxes import models as sandboxes
from bank_sim.modules.scenarios import models as scenarios
from bank_sim.modules.sources import models as sources
from bank_sim.modules.staff import models as staff
from bank_sim.modules.transfers import models as transfers

MODEL_MODULES = (
    sandboxes,
    personas,
    staff,
    sources,
    conveyor,
    core_banking,
    failures,
    outbox,
    notifications,
    program_platform,
    borrower_app,
    cards,
    transfers,
    incidents,
    scenarios,
)
metadata = Base.metadata
