"""Все таблицы якоря — для миграций."""

from anchor.database import Base
from anchor.modules.checkpoints import models as checkpoints

MODEL_MODULES = (checkpoints,)
metadata = Base.metadata
