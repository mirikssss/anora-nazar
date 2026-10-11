"""Таблицы модуля."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class StaffRole(Base):
    __tablename__ = "staff_roles"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    home_path: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(String(512))
    permissions: Mapped[list[str]] = mapped_column(JSONB)
    restrictions: Mapped[list[str]] = mapped_column(JSONB)


class StaffUser(Base):
    __tablename__ = "staff_users"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("staff_roles.code"))
    display_name: Mapped[str] = mapped_column(String(128))
    division: Mapped[str] = mapped_column(String(256))
    branch_id: Mapped[str | None] = mapped_column(String(32))  # сотрудник филиала: не ведёт дела своего филиала


class ApiClient(Base):
    __tablename__ = "api_clients"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSONB)
