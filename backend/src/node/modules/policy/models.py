"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class PolicyProposal(Base):
    """Предложение изменить пороги: кто предложил, что и почему; утверждает другой сотрудник."""

    __tablename__ = "policy_proposals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[str] = mapped_column(String(64))
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    proposed_by: Mapped[str] = mapped_column(String(64))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resulting_version: Mapped[str | None] = mapped_column(String(64))


class PolicyVersion(Base):
    """Утверждённая версия политики контура: полное содержимое и хеш — для решений и их воспроизведения."""

    __tablename__ = "policy_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
