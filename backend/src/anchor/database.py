"""База якоря: метаданные и базовый класс моделей."""

from sqlalchemy.orm import DeclarativeBase

from shared.db import make_metadata


class Base(DeclarativeBase):
    metadata = make_metadata()
