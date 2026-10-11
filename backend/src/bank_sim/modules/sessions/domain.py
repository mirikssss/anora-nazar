"""Сводка сессионного антифрода по сессии заявки (№ 3759 п. 36–38) из профиля сессии клиента."""

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts.facts import SessionSummary


class SessionProfile(BaseModel):
    """Что видел сессионный антифрод в сессии заявки: возраст устройства, восстановление доступа, звонок."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_age_days: int = Field(ge=0)
    access_recovered_minutes_before: int | None = Field(default=None, ge=0)
    remote_control: bool = False
    call_in_progress: bool = False
    form_seconds: int | None = Field(default=None, ge=0)
    pasted: bool | None = None


def session_summary(
    pinfl: str, application_id: str, device_id: str, profile: SessionProfile, now: datetime
) -> SessionSummary:
    recovered = profile.access_recovered_minutes_before
    return SessionSummary(
        subject_pinfl=pinfl,
        application_id=application_id,
        device_id=device_id,
        device_first_seen_at=now - timedelta(days=profile.device_age_days),
        access_recovered_at=None if recovered is None else now - timedelta(minutes=recovered),
        remote_control=profile.remote_control,
        call_in_progress=profile.call_in_progress,
        form_seconds=profile.form_seconds,
        pasted=profile.pasted,
    )
