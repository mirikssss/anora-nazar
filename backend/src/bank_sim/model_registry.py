"""Все таблицы имитатора банка — для миграций."""

from bank_sim.database import Base
from bank_sim.modules.conveyor import models as conveyor
from bank_sim.modules.core_banking import models as core_banking
from bank_sim.modules.failures import models as failures
from bank_sim.modules.notifications import models as notifications
from bank_sim.modules.outbox import models as outbox
from bank_sim.modules.personas import models as personas
from bank_sim.modules.sandboxes import models as sandboxes
from bank_sim.modules.sources import models as sources
from bank_sim.modules.staff import models as staff

MODEL_MODULES = (sandboxes, personas, staff, sources, conveyor, core_banking, failures, outbox, notifications)
metadata = Base.metadata
