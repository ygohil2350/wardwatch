import { useEffect, useState } from "react";
import { METRICS, type Bands, type Patient, type Reading } from "../api";
import VitalChart from "./VitalChart";

type Props = { patient: Patient; readings: Reading[]; bands: Bands | null };

export default function PatientPanel({ patient, readings, bands }: Props) {
  // Re-render each second so the time axis keeps sliding even between readings.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  return (
    <section className="panel" aria-labelledby="panel-title">
      <header className="panel-head">
        <h2 id="panel-title">
          <span className="mono">{patient.bed}</span> {patient.name}
        </h2>
        <p>
          {patient.age} years · {patient.reason}
        </p>
      </header>
      <div className="charts">
        {METRICS.map((m) => (
          <VitalChart
            key={m.key}
            metric={m.key}
            label={m.label}
            unit={m.unit}
            domain={m.domain}
            readings={readings}
            bands={bands}
            now={now}
          />
        ))}
      </div>
      <p className="legend">
        <span className="swatch z-warning" /> warning band <span className="swatch z-critical" /> critical band · bands
        loosely adapted from NEWS2, simplified for this demo
      </p>
    </section>
  );
}
