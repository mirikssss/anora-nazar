"""Таблицы модуля."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from network_operator.database import Base


class ApiClient(Base):
    """Ключ кредитора или системы стенда: в базе только хеш, права — из сидов."""

    __tablename__ = "api_clients"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    lender: Mapped[str | None] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSONB)
