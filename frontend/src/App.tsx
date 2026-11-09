import { useEffect, useState } from "react";
import { useWard, type Connection } from "./useWard";
import WardTable from "./components/WardTable";
import AlertQueue from "./components/AlertQueue";
import PatientPanel from "./components/PatientPanel";

const CONNECTION_TEXT: Record<Connection, string> = {
  live: "Live",
  reconnecting: "Reconnecting…",
  waking: "Waking the server…",
};

export default function App() {
  const ward = useWard();
  const [selected, setSelected] = useState<number | null>(null);
  const { loadHistory } = ward;

  // Default to the first bed once the ward has loaded.
  useEffect(() => {
    if (selected === null && ward.patients.length) setSelected(ward.patients[0].id);
  }, [selected, ward.patients]);

  useEffect(() => {
    if (selected !== null) loadHistory(selected);
  }, [selected, loadHistory]);

  const patient = ward.patients.find((p) => p.id === selected);

  return (
    <>
      <header className="top">
        <div className="brand">
          <strong>Wardwatch</strong>
          <span>Ward 4B · 8 beds · simulated monitors, not real patients</span>
        </div>
        <p className={`conn conn-${ward.connection}`} role="status">
          <span className="dot" aria-hidden="true" />
          {CONNECTION_TEXT[ward.connection]}
        </p>
      </header>

      {ward.patients.length === 0 ? (
        <main className="waking">
          <h1>Starting up</h1>
          <p>
            The API runs on free hosting that sleeps when nobody is using it. The first request wakes it, which takes
            about 30–60 seconds. This page will fill in by itself.
          </p>
        </main>
      ) : (
        <main className="layout">
          <h1 className="sr-only">Ward 4B vitals</h1>
          <div className="main-col">
            <WardTable
              patients={ward.patients}
              bands={ward.bands}
              history={ward.history}
              open={ward.open}
              selected={selected}
              onSelect={setSelected}
            />
            {patient && <PatientPanel patient={patient} readings={ward.history[patient.id] ?? []} bands={ward.bands} />}
          </div>
          <AlertQueue
            open={ward.open}
            acked={ward.acked}
            patients={ward.patients}
            onAcknowledged={ward.applyAlert}
            onSelect={setSelected}
          />
        </main>
      )}

      <footer className="foot">
        Demo by{" "}
        <a href="https://yash-gohil-portfolio.netlify.app" target="_blank" rel="noreferrer">
          Yash Gohil
        </a>{" "}
        ·{" "}
        <a href="https://github.com/ygohil2350/wardwatch" target="_blank" rel="noreferrer">
          source
        </a>
      </footer>
    </>
  );
}
