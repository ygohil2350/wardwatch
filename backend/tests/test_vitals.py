import pytest

from app.vitals import classify, is_worse, worst_level


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        ("hr", 75, "normal"),
        ("hr", 111, "warning"),
        ("hr", 110, "normal"),
        ("hr", 131, "critical"),
        ("hr", 50, "warning"),
        ("hr", 40, "critical"),
        ("spo2", 94, "normal"),
        ("spo2", 93, "warning"),
        ("spo2", 91, "critical"),
        ("sys", 101, "normal"),
        ("sys", 100, "warning"),
        ("sys", 90, "critical"),
        ("sys", 220, "critical"),
        ("rr", 20, "normal"),
        ("rr", 21, "warning"),
        ("rr", 25, "critical"),
        ("rr", 8, "critical"),
        ("temp", 37.0, "normal"),
        ("temp", 39.1, "warning"),
        ("temp", 36.0, "warning"),
        ("temp", 35.0, "critical"),
    ],
)
def test_band_edges(metric, value, expected):
    assert classify(metric, value) == expected


def test_worse_depends_on_which_side_is_breached():
    assert is_worse("spo2", 88, 90)  # lower saturation is worse
    assert not is_worse("spo2", 92, 90)
    assert is_worse("hr", 140, 130)  # higher rate is worse on the high side
    assert is_worse("hr", 38, 45)  # lower rate is worse on the low side


def test_worst_level_takes_the_most_severe_metric():
    values = {"hr": 80, "spo2": 92, "sys": 120, "rr": 26, "temp": 37}
    assert worst_level(values) == "critical"
