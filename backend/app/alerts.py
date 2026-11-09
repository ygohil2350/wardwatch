"""Turns a stream of readings into alerts.

Rules:
- A metric must be out of band for PERSIST consecutive readings before an alert opens, so one noisy
  sample (a loose probe, a patient moving) doesn't page anyone.
- One open alert per patient + metric. While it's open, further abnormal readings update its level
  (warning -> critical) and its worst value instead of opening duplicates.
- After a nurse acknowledges, that metric is quiet for that patient until it either returns to normal
  (then it can alert again later) or gets worse than the level that was acknowledged.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Alert, Reading
from .vitals import METRICS, RANK, Level, classify, is_worse

Key = tuple[int, str]
PERSIST = 3  # readings; at one every 2 s that is 6 s out of band


@dataclass
class AlertEngine:
    persist: int = PERSIST
    open_ids: dict[Key, int] = field(default_factory=dict)
    acknowledged_at_level: dict[Key, Level] = field(default_factory=dict)
    streak: dict[Key, int] = field(default_factory=dict)

    async def load(self, session: AsyncSession) -> None:
        rows = await session.execute(select(Alert.id, Alert.patient_id, Alert.metric).where(Alert.acknowledged_at.is_(None)))
        self.open_ids = {(pid, metric): aid for aid, pid, metric in rows.all()}

    def on_acknowledged(self, alert: Alert) -> None:
        key = (alert.patient_id, alert.metric)
        if self.open_ids.get(key) == alert.id:
            del self.open_ids[key]
        self.acknowledged_at_level[key] = alert.level  # type: ignore[assignment]

    async def evaluate(self, session: AsyncSession, reading: Reading) -> list[Alert]:
        """Apply one reading. Returns alerts that were created or changed (caller commits)."""
        changed: list[Alert] = []
        for metric in METRICS:
            value = float(getattr(reading, metric))
            level = classify(metric, value)
            key = (reading.patient_id, metric)

            if level == "normal":
                self.acknowledged_at_level.pop(key, None)
                self.streak.pop(key, None)
                continue
            self.streak[key] = self.streak.get(key, 0) + 1

            acked_level = self.acknowledged_at_level.get(key)
            if acked_level is not None:
                if RANK[level] <= RANK[acked_level]:
                    continue
                del self.acknowledged_at_level[key]

            open_id = self.open_ids.get(key)
            if open_id is not None:
                alert = await session.get(Alert, open_id)
                if alert is None or alert.acknowledged_at is not None:
                    self.open_ids.pop(key, None)
                else:
                    touched = False
                    if RANK[level] > RANK[alert.level]:  # type: ignore[index]
                        alert.level = level
                        touched = True
                    if is_worse(metric, value, alert.worst_value):
                        alert.worst_value = value
                        touched = True
                    if touched:
                        changed.append(alert)
                    continue

            if self.streak[key] < self.persist:
                continue
            alert = Alert(patient_id=reading.patient_id, metric=metric, level=level, worst_value=value)
            session.add(alert)
            await session.flush()
            self.open_ids[key] = alert.id
            changed.append(alert)
        return changed
