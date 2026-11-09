import { useEffect, useState, type FormEvent } from "react";
import { ApiError, METRICS, api, formatValue, type Alert, type Patient } from "../api";

type Props = {
  open: Alert[];
  acked: Alert[];
  patients: Patient[];
  onAcknowledged: (alert: Alert) => void;
  onSelect: (patientId: number) => void;
};

const NAME_KEY = "wardwatch.nurse";

function readName() {
  try {
    return localStorage.getItem(NAME_KEY) ?? "";
  } catch {
    return "";
  }
}

function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return now;
}

function waited(fromIso: string, now: number) {
  const s = Math.max(0, Math.floor((now - new Date(fromIso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ${s % 60}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

function clock(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const meta = Object.fromEntries(METRICS.map((m) => [m.key, m]));

export default function AlertQueue({ open, acked, patients, onAcknowledged, onSelect }: Props) {
  const now = useNow();
  const [acking, setAcking] = useState<number | null>(null);
  const bed = (id: number) => patients.find((p) => p.id === id);

  const queue = [...open].sort((a, b) =>
    a.level !== b.level ? (a.level === "critical" ? -1 : 1) : a.opened_at.localeCompare(b.opened_at),
  );

  return (
    <section className="queue" aria-labelledby="queue-title">
      <h2 id="queue-title">
        Needs acknowledging <span className="count">{queue.length}</span>
      </h2>

      {queue.length === 0 ? (
        <p className="empty">Nothing waiting. A reading outside its band shows up here within two seconds.</p>
      ) : (
        <ol className="alerts">
          {queue.map((a) => {
            const p = bed(a.patient_id);
            const m = meta[a.metric];
            return (
              <li key={a.id} className={`alert a-${a.level}`}>
                <div className="alert-top">
                  <span className="level">{a.level === "critical" ? "Critical" : "Warning"}</span>
                  <span className="waited">open {waited(a.opened_at, now)}</span>
                </div>
                <p className="alert-what">
                  <button type="button" className="link" onClick={() => onSelect(a.patient_id)}>
                    {p?.bed} {p?.name}
                  </button>
                </p>
                <p className="alert-value">
                  {m.label} <strong>{formatValue(a.metric, a.worst_value)}</strong> {m.unit}
                  <span> worst so far</span>
                </p>
                {acking === a.id ? (
                  <AckForm
                    alert={a}
                    onDone={(updated) => {
                      setAcking(null);
                      onAcknowledged(updated);
                    }}
                    onCancel={() => setAcking(null)}
                  />
                ) : (
                  <button type="button" className="btn" onClick={() => setAcking(a.id)}>
                    Acknowledge
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      )}

      <h3 className="acked-title">Recently acknowledged</h3>
      {acked.length === 0 ? (
        <p className="empty">None yet.</p>
      ) : (
        <ul className="acked">
          {acked.map((a) => {
            const p = bed(a.patient_id);
            return (
              <li key={a.id}>
                <span className="mono">{a.acknowledged_at && clock(a.acknowledged_at)}</span> {a.acknowledged_by} ·{" "}
                {p?.bed} {meta[a.metric].short} {formatValue(a.metric, a.worst_value)}
                {a.note && <q>{a.note}</q>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function AckForm({ alert, onDone, onCancel }: { alert: Alert; onDone: (a: Alert) => void; onCancel: () => void }) {
  const [name, setName] = useState(readName);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) {
      setError("Enter your name so the ward knows who saw this.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.acknowledge(alert.id, name.trim(), note);
      try {
        localStorage.setItem(NAME_KEY, name.trim());
      } catch {
        /* storage unavailable: fine */
      }
      onDone(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(`${err.message}. Refreshing the queue.`);
        window.setTimeout(onCancel, 1800);
      } else {
        setError(err instanceof ApiError ? err.message : "Couldn't reach the server. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  const nameId = `ack-name-${alert.id}`;
  const noteId = `ack-note-${alert.id}`;
  const errId = `ack-err-${alert.id}`;
  return (
    <form className="ack" onSubmit={submit} noValidate>
      <label htmlFor={nameId}>Your name</label>
      <input
        id={nameId}
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={40}
        autoComplete="name"
        autoFocus
        aria-invalid={!!error && name.trim().length < 2}
        aria-describedby={error ? errId : undefined}
      />
      <label htmlFor={noteId}>
        Note <span className="opt">optional</span>
      </label>
      <textarea id={noteId} value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} rows={2} />
      {error && (
        <p id={errId} className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="ack-actions">
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Saving…" : "Acknowledge alert"}
        </button>
        <button type="button" className="link" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
