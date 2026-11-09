import asyncio

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import alert_engine, app
from app.models import Alert, Reading

NORMAL = {"hr": 80, "spo2": 97, "sys": 120, "dia": 75, "rr": 16, "temp": 37.0}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def feed(patient_id: int, times: int = 1, **overrides) -> list[Alert]:
    async def go():
        changed: list[Alert] = []
        async with SessionLocal() as s:
            for _ in range(times):
                r = Reading(patient_id=patient_id, **{**NORMAL, **overrides})
                s.add(r)
                await s.flush()
                changed += await alert_engine.evaluate(s, r)
            await s.commit()
            return changed

    return asyncio.run(go())


P = alert_engine.persist  # readings needed before an alert opens


def open_alerts(client, patient_id: int, metric: str):
    return [a for a in client.get("/api/alerts").json() if a["patient_id"] == patient_id and a["metric"] == metric]


def test_patients_are_seeded(client):
    patients = client.get("/api/patients").json()
    assert len(patients) == 8
    assert patients[0]["bed"] == "4B-01"


def test_short_blip_does_not_alert(client):
    feed(6, times=P - 1, hr=140)
    feed(6)  # back to normal before the alert would have opened
    feed(6, times=P - 1, hr=140)
    assert open_alerts(client, 6, "hr") == []


def test_repeated_abnormal_readings_update_one_alert(client):
    feed(1, times=P, spo2=93)
    feed(1, spo2=91)
    feed(1, spo2=89)
    alerts = open_alerts(client, 1, "spo2")
    assert len(alerts) == 1
    assert alerts[0]["level"] == "critical"
    assert alerts[0]["worst_value"] == 89


def test_ack_silences_until_worse_or_recovered(client):
    feed(2, times=P, hr=115)  # warning
    [alert] = open_alerts(client, 2, "hr")

    r = client.post(f"/api/alerts/{alert['id']}/ack", json={"by": "Nurse Priya", "note": "  "})
    assert r.status_code == 200
    assert r.json()["acknowledged_by"] == "Nurse Priya"
    assert r.json()["note"] is None

    feed(2, hr=118)  # still warning: stays quiet
    assert open_alerts(client, 2, "hr") == []

    feed(2, hr=135)  # escalates to critical: alerts again
    [again] = open_alerts(client, 2, "hr")
    assert again["level"] == "critical"


def test_recovery_resets_suppression(client):
    feed(3, times=P, rr=22)
    [alert] = open_alerts(client, 3, "rr")
    client.post(f"/api/alerts/{alert['id']}/ack", json={"by": "Sam"})
    feed(3, rr=16)  # back to normal
    feed(3, times=P, rr=22)  # same level as before, but it recovered in between
    assert len(open_alerts(client, 3, "rr")) == 1


def test_second_ack_conflicts(client):
    feed(4, times=P, temp=39.4)
    [alert] = open_alerts(client, 4, "temp")
    first = client.post(f"/api/alerts/{alert['id']}/ack", json={"by": "Asha"})
    second = client.post(f"/api/alerts/{alert['id']}/ack", json={"by": "Ben"})
    assert first.status_code == 200
    assert second.status_code == 409
    assert "Asha" in second.json()["detail"]


def test_ack_validation_and_missing(client):
    assert client.post("/api/alerts/999999/ack", json={"by": "Asha"}).status_code == 404
    assert client.post("/api/alerts/1/ack", json={"by": " a "}).status_code == 422


def test_readings_window(client):
    feed(5)
    rows = client.get("/api/patients/5/readings?minutes=5").json()
    assert rows and rows[-1]["patient_id"] == 5
    assert client.get("/api/patients/5/readings?minutes=99").status_code == 422
    assert client.get("/api/patients/999/readings").status_code == 404
