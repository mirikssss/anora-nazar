"""База узла: метаданные и базовый класс моделей всех модулей."""

from sqlalchemy.orm import DeclarativeBase

from shared.db import make_metadata


class Base(DeclarativeBase):
    metadata = make_metadata()
