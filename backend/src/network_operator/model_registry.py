"""Все таблицы оператора — для миграций."""

from network_operator.database import Base
from network_operator.modules.activity import models as activity
from network_operator.modules.clients import models as clients
from network_operator.modules.confirmed import models as confirmed
from network_operator.modules.quotas import models as quotas
from network_operator.modules.realms import models as realms
from network_operator.modules.watches import models as watches

MODEL_MODULES = (activity, clients, confirmed, quotas, realms, watches)
metadata = Base.metadata
