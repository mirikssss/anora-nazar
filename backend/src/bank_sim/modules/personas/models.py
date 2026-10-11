"""Таблицы модуля."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class BankRole(Base):
    __tablename__ = "bank_roles"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    home_path: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(String(512))
    permissions: Mapped[list[str]] = mapped_column(JSONB)
    restrictions: Mapped[list[str]] = mapped_column(JSONB)
