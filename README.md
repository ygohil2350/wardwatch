# Wardwatch

A live vitals board for one hospital ward. Eight simulated bedside monitors stream heart rate, SpO₂,
blood pressure, respiratory rate and temperature every two seconds. The server scores each reading
against warning and critical bands, opens alerts, and keeps them open until a nurse acknowledges
them by name.

**Everything is simulated.** Patients, names and readings are invented; the bands are loosely
adapted from the UK NEWS2 early-warning score and simplified to two levels. Not clinical software.

## What's worth looking at

- **Alerts need to persist before they open.** A metric has to be out of band for three readings in a
  row (6 s) before anyone is alerted, so a single noisy sample doesn't page the ward. Once an alert
  is open it escalates from warning to critical immediately.
- **One alert per patient and metric.** Further bad readings update the open alert's level and its
  worst value instead of stacking duplicates.
- **Acknowledging quiets a metric, it doesn't mute it.** After an ack, the same metric stays quiet
  until it either recovers (and can alert again later) or gets worse than the level that was
  acknowledged.
- **Two nurses can't acknowledge the same alert.** The ack is a conditional
  `UPDATE … WHERE acknowledged_at IS NULL`; the loser gets a `409` naming who got there first.
- **One source of truth for thresholds.** The UI colours values with the bands it fetches from
  `/api/thresholds`, the same ones the server alerts on.
- **Status is always written out.** Critical / Watch / Stable appear as text; colour is a second
  channel, never the only one.
- **Charts are plain SVG.** Ten-minute sliding windows with the warning and critical bands shaded,
  no chart library.

## Stack

| Part | Tech |
|---|---|
| API | FastAPI, SQLAlchemy 2 (async), Pydantic, WebSockets |
| Database | PostgreSQL in production (Neon), SQLite locally and in tests |
| Web | React 18, TypeScript, Vite, no UI kit |
| Hosting | Render (API), Vercel (web) |

## Run it locally

```bash
# API: http://localhost:8000
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Web: http://localhost:5173
cd frontend
npm install
npm run dev
```

With no `DATABASE_URL` set, the API uses a local SQLite file and seeds the ward on first start.

```bash
cd backend && pytest
```

## Configuration

| Variable | Where | Default |
|---|---|---|
| `DATABASE_URL` | API | `sqlite+aiosqlite:///./wardwatch.db`. A plain `postgres://` URL is accepted and switched to the async driver. |
| `CORS_ORIGINS` | API | `http://localhost:5173`, comma-separated |
| `SIMULATE` | API | `true` |
| `VITE_API_URL` | Web | `http://localhost:8000` |

## Limits

- Live updates fan out from memory, which is right for a single API process. Several replicas would
  need a shared channel (Postgres `LISTEN/NOTIFY` or Redis).
- Readings older than 30 minutes are pruned, and acknowledged alerts after six hours, to stay inside
  free database storage.
- On the free Render plan the API sleeps after 15 idle minutes; the first visit wakes it in roughly
  30–60 seconds, and the page says so while it waits.
