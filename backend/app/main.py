import asyncio
import logging
import random
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .alerts import AlertEngine
from .config import get_settings
from .db import Base, SessionLocal, engine, get_session
from .hub import hub
from .models import Alert, Patient, Reading, utcnow
from .schemas import AckIn, AlertOut, PatientOut, ReadingOut
from .simulator import PATIENTS, Monitor
from .vitals import BANDS, RANK

log = logging.getLogger("wardwatch")
settings = get_settings()
alert_engine = AlertEngine()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        if not await session.scalar(select(func.count(Patient.id))):
            session.add_all(Patient(**{k: v for k, v in p.items() if k != "base"}) for p in PATIENTS)
            await session.commit()
        await alert_engine.load(session)


async def simulate_forever() -> None:
    rng = random.Random()
    async with SessionLocal() as session:
        beds = {p.bed: p.id for p in (await session.scalars(select(Patient))).all()}
    monitors = {beds[p["bed"]]: Monitor(base=dict(p["base"])) for p in PATIENTS if p["bed"] in beds}
    ticks = 0

    while True:
        try:
            async with SessionLocal() as session:
                readings = [Reading(patient_id=pid, **m.step(rng)) for pid, m in monitors.items()]
                session.add_all(readings)
                await session.flush()
                changed = []
                for r in readings:
                    changed.extend(await alert_engine.evaluate(session, r))
                await session.commit()

                if ticks % 30 == 0:
                    cutoff = utcnow() - timedelta(minutes=settings.keep_minutes)
                    await session.execute(delete(Reading).where(Reading.taken_at < cutoff))
                    await session.execute(
                        delete(Alert).where(Alert.acknowledged_at.is_not(None), Alert.opened_at < utcnow() - timedelta(hours=6))
                    )
                    await session.commit()

            await hub.broadcast(
                {"type": "readings", "readings": [ReadingOut.model_validate(r).model_dump(mode="json") for r in readings]}
            )
            for a in changed:
                await hub.broadcast({"type": "alert", "alert": AlertOut.model_validate(a).model_dump(mode="json")})
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("simulation tick failed")
        ticks += 1
        await asyncio.sleep(settings.tick_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    task = asyncio.create_task(simulate_forever()) if settings.simulate else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await engine.dispose()


app = FastAPI(title="Wardwatch API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "simulating": settings.simulate, "listeners": hub.size}


@app.get("/api/thresholds")
async def thresholds() -> dict:
    """The UI colours values with the same bands the server alerts on, so there's one source of truth."""
    return {metric: asdict(band) for metric, band in BANDS.items()}


@app.get("/api/patients", response_model=list[PatientOut])
async def list_patients(session: AsyncSession = Depends(get_session)) -> list[PatientOut]:
    patients = (await session.scalars(select(Patient).order_by(Patient.bed))).all()
    latest_ids = select(func.max(Reading.id)).group_by(Reading.patient_id)
    latest = {r.patient_id: r for r in (await session.scalars(select(Reading).where(Reading.id.in_(latest_ids)))).all()}
    return [
        PatientOut.model_validate(p).model_copy(
            update={"latest": ReadingOut.model_validate(latest[p.id]) if p.id in latest else None}
        )
        for p in patients
    ]


@app.get("/api/patients/{patient_id}/readings", response_model=list[ReadingOut])
async def patient_readings(
    patient_id: int,
    minutes: int = Query(default=10, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
) -> list[Reading]:
    if not await session.get(Patient, patient_id):
        raise HTTPException(404, "No such patient")
    since = utcnow() - timedelta(minutes=minutes)
    rows = await session.scalars(
        select(Reading).where(Reading.patient_id == patient_id, Reading.taken_at >= since).order_by(Reading.taken_at)
    )
    return list(rows.all())


@app.get("/api/alerts", response_model=list[AlertOut])
async def list_alerts(
    status: str = Query(default="open", pattern="^(open|acknowledged)$"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[Alert]:
    if status == "open":
        rows = (await session.scalars(select(Alert).where(Alert.acknowledged_at.is_(None)))).all()
        # Critical first, then whoever has waited longest.
        return sorted(rows, key=lambda a: (-RANK[a.level], a.opened_at))[:limit]  # type: ignore[index]
    rows = await session.scalars(
        select(Alert).where(Alert.acknowledged_at.is_not(None)).order_by(Alert.acknowledged_at.desc()).limit(limit)
    )
    return list(rows.all())


@app.post("/api/alerts/{alert_id}/ack", response_model=AlertOut)
async def acknowledge(alert_id: int, body: AckIn, session: AsyncSession = Depends(get_session)) -> Alert:
    # Conditional update: if two nurses press Acknowledge at once, exactly one wins and the other gets 409.
    result = await session.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.acknowledged_at.is_(None))
        .values(acknowledged_at=utcnow(), acknowledged_by=body.by, note=body.note)
    )
    await session.commit()
    alert = await session.get(Alert, alert_id, populate_existing=True)
    if alert is None:
        raise HTTPException(404, "No such alert")
    if result.rowcount == 0:
        raise HTTPException(409, f"Already acknowledged by {alert.acknowledged_by}")

    alert_engine.on_acknowledged(alert)
    await hub.broadcast({"type": "alert", "alert": AlertOut.model_validate(alert).model_dump(mode="json")})
    return alert


@app.websocket("/ws")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    await hub.join(ws)
    try:
        while True:
            await ws.receive_text()  # clients don't send anything meaningful; this just waits for disconnect
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(ws)
