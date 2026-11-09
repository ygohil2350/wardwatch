from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator


def _as_utc(value: datetime | None) -> datetime | None:
    # SQLite drops tzinfo on the way back out; everything is stored as UTC, so say so.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    taken_at: UtcDatetime
    hr: int
    spo2: int
    sys: int
    dia: int
    rr: int
    temp: float


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bed: str
    name: str
    age: int
    reason: str
    latest: ReadingOut | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    metric: str
    level: str
    worst_value: float
    opened_at: UtcDatetime
    acknowledged_at: UtcDatetime | None
    acknowledged_by: str | None
    note: str | None


class AckIn(BaseModel):
    by: str = Field(min_length=2, max_length=40)
    note: str | None = Field(default=None, max_length=200)

    @field_validator("by")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least 2 characters")
        return value

    @field_validator("note")
    @classmethod
    def blank_note_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None
