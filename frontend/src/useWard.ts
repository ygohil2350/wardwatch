import { useCallback, useEffect, useReducer, useRef } from "react";
import { api, WS_URL, type Alert, type Bands, type Patient, type Reading } from "./api";

const HISTORY_POINTS = 300; // 10 minutes at one reading every 2 s

export type Connection = "waking" | "live" | "reconnecting";

type State = {
  connection: Connection;
  bands: Bands | null;
  patients: Patient[];
  history: Record<number, Reading[]>;
  open: Alert[];
  acked: Alert[];
};

type Action =
  | { type: "loaded"; bands: Bands; patients: Patient[]; open: Alert[]; acked: Alert[] }
  | { type: "alerts"; open: Alert[]; acked: Alert[] }
  | { type: "connection"; connection: Connection }
  | { type: "readings"; readings: Reading[] }
  | { type: "history"; patientId: number; readings: Reading[] }
  | { type: "alert"; alert: Alert };

function byTime(a: Reading, b: Reading) {
  return a.taken_at < b.taken_at ? -1 : a.taken_at > b.taken_at ? 1 : 0;
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "loaded":
      return { ...state, bands: action.bands, patients: action.patients, open: action.open, acked: action.acked };
    case "alerts":
      return { ...state, open: action.open, acked: action.acked };
    case "connection":
      return { ...state, connection: action.connection };
    case "readings": {
      const latest = new Map(action.readings.map((r) => [r.patient_id, r]));
      const history = { ...state.history };
      for (const r of action.readings) {
        const prev = history[r.patient_id] ?? [];
        history[r.patient_id] = [...prev.slice(-(HISTORY_POINTS - 1)), r];
      }
      return {
        ...state,
        history,
        patients: state.patients.map((p) => (latest.has(p.id) ? { ...p, latest: latest.get(p.id)! } : p)),
      };
    }
    case "history": {
      // Merge fetched history with whatever arrived over the socket in the meantime.
      const seen = new Set(action.readings.map((r) => r.taken_at));
      const live = (state.history[action.patientId] ?? []).filter((r) => !seen.has(r.taken_at));
      const merged = [...action.readings, ...live].sort(byTime).slice(-HISTORY_POINTS);
      return { ...state, history: { ...state.history, [action.patientId]: merged } };
    }
    case "alert": {
      const a = action.alert;
      const open = state.open.filter((x) => x.id !== a.id);
      if (a.acknowledged_at) {
        const acked = [a, ...state.acked.filter((x) => x.id !== a.id)].slice(0, 8);
        return { ...state, open, acked };
      }
      return { ...state, open: [...open, a] };
    }
  }
}

const initial: State = { connection: "waking", bands: null, patients: [], history: {}, open: [], acked: [] };

export function useWard() {
  const [state, dispatch] = useReducer(reducer, initial);
  const loaded = useRef(false);

  // First load retries patiently: on free hosting the API may be asleep and take ~30–60 s to wake.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let attempt = 0; !cancelled; attempt++) {
        try {
          const [bands, patients, open, acked] = await Promise.all([
            api.thresholds(),
            api.patients(),
            api.openAlerts(),
            api.recentAcks(),
          ]);
          if (cancelled) return;
          loaded.current = true;
          dispatch({ type: "loaded", bands, patients, open, acked });
          return;
        } catch {
          await new Promise((r) => setTimeout(r, Math.min(2000 + attempt * 1000, 6000)));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: number | undefined;
    let stopped = false;

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        retry = 0;
        dispatch({ type: "connection", connection: "live" });
        // Anything that changed while we were disconnected.
        if (loaded.current) {
          Promise.all([api.openAlerts(), api.recentAcks()])
            .then(([open, acked]) => dispatch({ type: "alerts", open, acked }))
            .catch(() => {});
        }
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "readings") dispatch({ type: "readings", readings: msg.readings });
        else if (msg.type === "alert") dispatch({ type: "alert", alert: msg.alert });
      };
      ws.onclose = () => {
        if (stopped) return;
        dispatch({ type: "connection", connection: loaded.current ? "reconnecting" : "waking" });
        timer = window.setTimeout(connect, Math.min(1000 * 2 ** retry++, 10000));
      };
    };
    connect();

    return () => {
      stopped = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, []);

  const loadHistory = useCallback(async (patientId: number) => {
    try {
      dispatch({ type: "history", patientId, readings: await api.readings(patientId, 10) });
    } catch {
      /* the live stream will fill the chart anyway */
    }
  }, []);

  const applyAlert = useCallback((alert: Alert) => dispatch({ type: "alert", alert }), []);

  return { ...state, loadHistory, applyAlert };
}
