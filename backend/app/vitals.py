"""Threshold scoring. Pure functions only, so the rules can be tested without a database.

Bands are loosely adapted from the UK NEWS2 early-warning score and simplified to two levels
for this demo. They are not clinical guidance.
"""

from dataclasses import dataclass
from typing import Literal

Level = Literal["normal", "warning", "critical"]
METRICS = ("hr", "spo2", "sys", "rr", "temp")
RANK: dict[Level, int] = {"normal": 0, "warning": 1, "critical": 2}


@dataclass(frozen=True)
class Band:
    critical_low: float | None
    warning_low: float | None
    warning_high: float | None
    critical_high: float | None


# A value at or beyond a bound is in that band. None means "no bound on this side".
BANDS: dict[str, Band] = {
    "hr": Band(critical_low=40, warning_low=50, warning_high=111, critical_high=131),
    "spo2": Band(critical_low=91, warning_low=93, warning_high=None, critical_high=None),
    "sys": Band(critical_low=90, warning_low=100, warning_high=None, critical_high=220),
    "rr": Band(critical_low=8, warning_low=None, warning_high=21, critical_high=25),
    "temp": Band(critical_low=35.0, warning_low=36.0, warning_high=39.1, critical_high=None),
}


def classify(metric: str, value: float) -> Level:
    b = BANDS[metric]
    if (b.critical_low is not None and value <= b.critical_low) or (
        b.critical_high is not None and value >= b.critical_high
    ):
        return "critical"
    if (b.warning_low is not None and value <= b.warning_low) or (
        b.warning_high is not None and value >= b.warning_high
    ):
        return "warning"
    return "normal"


def is_worse(metric: str, candidate: float, current: float) -> bool:
    """Is `candidate` further from normal than `current`? Direction depends on which bound is breached."""
    b = BANDS[metric]
    low_side = b.warning_low if b.warning_low is not None else b.critical_low
    if low_side is not None and candidate <= low_side:
        return candidate < current
    return candidate > current


def worst_level(values: dict[str, float]) -> Level:
    levels = [classify(m, values[m]) for m in METRICS]
    return max(levels, key=lambda lv: RANK[lv])
