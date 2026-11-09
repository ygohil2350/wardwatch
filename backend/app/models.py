from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    bed: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    age: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120))


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_patient_time", "patient_id", "taken_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    hr: Mapped[int] = mapped_column(Integer)
    spo2: Mapped[int] = mapped_column(Integer)
    sys: Mapped[int] = mapped_column(Integer)
    dia: Mapped[int] = mapped_column(Integer)
    rr: Mapped[int] = mapped_column(Integer)
    temp: Mapped[float] = mapped_column(Float)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_open", "acknowledged_at", "opened_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(8))
    level: Mapped[str] = mapped_column(String(8))
    # The worst value seen while the alert was open, not just the value that opened it.
    worst_value: Mapped[float] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
