"""Все таблицы узла: импорт моделей модулей для миграций и метаданных."""

from node.database import Base
from node.modules.applications import models as applications
from node.modules.audit import models as audit
from node.modules.decisions import models as decisions
from node.modules.identity import models as identity
from node.modules.index import models as index
from node.modules.ingest import models as ingest
from node.modules.outbox import models as outbox
from node.modules.permits import models as permits
from node.modules.realms import models as realms
from node.modules.scoring import models as scoring
from shared.idempotency import idempotency_table

MODEL_MODULES = (realms, identity, applications, index, ingest, outbox, decisions, permits, audit, scoring)
metadata = Base.metadata
IDEMPOTENCY = idempotency_table(metadata, "realms")
