"""Таблицы модуля."""

from datetime import date
from typing import Any

from sqlalchemy import Date, String
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


class BorrowerPersona(Base):
    """Персона заёмщика для приложения банка в демо; профиль — JSON по модели PersonaProfile."""

    __tablename__ = "borrower_personas"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64))
    birth_date: Mapped[date] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(String(512))
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
