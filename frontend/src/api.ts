export type Metric = "hr" | "spo2" | "sys" | "rr" | "temp";
export type Level = "normal" | "warning" | "critical";

export type Reading = {
  patient_id: number;
  taken_at: string;
  hr: number;
  spo2: number;
  sys: number;
  dia: number;
  rr: number;
  temp: number;
};

export type Patient = {
  id: number;
  bed: string;
  name: string;
  age: number;
  reason: string;
  latest: Reading | null;
};

export type Alert = {
  id: number;
  patient_id: number;
  metric: Metric;
  level: Exclude<Level, "normal">;
  worst_value: number;
  opened_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  note: string | null;
};

export type Band = {
  critical_low: number | null;
  warning_low: number | null;
  warning_high: number | null;
  critical_high: number | null;
};
export type Bands = Record<Metric, Band>;

const API = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API.replace(/^http/, "ws") + "/ws";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Only send a JSON content type when there is a body: on GETs it would force a CORS preflight per request.
  const headers = init?.body ? { "Content-Type": "application/json" } : undefined;
  const res = await fetch(API + path, { ...init, headers });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : (body.detail?.[0]?.msg ?? message);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  patients: () => request<Patient[]>("/api/patients"),
  thresholds: () => request<Bands>("/api/thresholds"),
  readings: (patientId: number, minutes = 10) =>
    request<Reading[]>(`/api/patients/${patientId}/readings?minutes=${minutes}`),
  openAlerts: () => request<Alert[]>("/api/alerts?status=open"),
  recentAcks: () => request<Alert[]>("/api/alerts?status=acknowledged&limit=8"),
  acknowledge: (id: number, by: string, note: string) =>
    request<Alert>(`/api/alerts/${id}/ack`, { method: "POST", body: JSON.stringify({ by, note }) }),
};

// Same rule as the server: a value at or past a bound is in that band.
export function classify(bands: Bands | null, metric: Metric, value: number): Level {
  if (!bands) return "normal";
  const b = bands[metric];
  if ((b.critical_low !== null && value <= b.critical_low) || (b.critical_high !== null && value >= b.critical_high))
    return "critical";
  if ((b.warning_low !== null && value <= b.warning_low) || (b.warning_high !== null && value >= b.warning_high))
    return "warning";
  return "normal";
}

export const METRICS: { key: Metric; label: string; short: string; unit: string; domain: [number, number] }[] = [
  { key: "hr", label: "Heart rate", short: "HR", unit: "bpm", domain: [30, 170] },
  { key: "spo2", label: "Oxygen saturation", short: "SpO₂", unit: "%", domain: [80, 100] },
  { key: "sys", label: "Blood pressure", short: "BP", unit: "mmHg", domain: [40, 230] },
  { key: "rr", label: "Respiratory rate", short: "RR", unit: "/min", domain: [4, 34] },
  { key: "temp", label: "Temperature", short: "Temp", unit: "°C", domain: [34, 41] },
];

export function formatValue(metric: Metric, value: number): string {
  return metric === "temp" ? value.toFixed(1) : String(Math.round(value));
}
