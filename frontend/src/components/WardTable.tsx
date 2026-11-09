import { classify, formatValue, type Alert, type Bands, type Level, type Patient, type Reading } from "../api";
import Sparkline from "./Sparkline";

type Props = {
  patients: Patient[];
  bands: Bands | null;
  history: Record<number, Reading[]>;
  open: Alert[];
  selected: number | null;
  onSelect: (id: number) => void;
};

const STATUS_TEXT: Record<Level, string> = { critical: "Critical", warning: "Watch", normal: "Stable" };
const RANK: Record<Level, number> = { normal: 0, warning: 1, critical: 2 };

export default function WardTable({ patients, bands, history, open, selected, onSelect }: Props) {
  return (
    <div className="ward-scroll">
      <table className="ward">
        <caption className="sr-only">Ward 4B, latest reading per bed</caption>
        <thead>
          <tr>
            <th scope="col">Bed</th>
            <th scope="col">Patient</th>
            <th scope="col" className="num">HR</th>
            <th scope="col" className="num">SpO₂</th>
            <th scope="col" className="num">BP</th>
            <th scope="col" className="num">RR</th>
            <th scope="col" className="num">Temp</th>
            <th scope="col" className="trend">HR, last 2 min</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {patients.map((p) => {
            const r = p.latest;
            const lv = (m: "hr" | "spo2" | "sys" | "rr" | "temp") => (r ? classify(bands, m, r[m]) : "normal");
            const levels = r ? (["hr", "spo2", "sys", "rr", "temp"] as const).map(lv) : [];
            const worst = levels.reduce<Level>((w, l) => (RANK[l] > RANK[w] ? l : w), "normal");
            const pending = open.filter((a) => a.patient_id === p.id).length;
            return (
              <tr
                key={p.id}
                className={`row-${worst}${selected === p.id ? " is-selected" : ""}`}
                onClick={() => onSelect(p.id)}
              >
                <th scope="row">
                  <button type="button" className="bed" onClick={() => onSelect(p.id)} aria-pressed={selected === p.id}>
                    {p.bed}
                  </button>
                </th>
                <td className="who">
                  {p.name}
                  <span>
                    {p.age} · {p.reason}
                  </span>
                </td>
                {r ? (
                  <>
                    <td className={`num v-${lv("hr")}`}>{r.hr}</td>
                    <td className={`num v-${lv("spo2")}`}>{r.spo2}</td>
                    <td className={`num v-${lv("sys")}`}>
                      {r.sys}/{r.dia}
                    </td>
                    <td className={`num v-${lv("rr")}`}>{r.rr}</td>
                    <td className={`num v-${lv("temp")}`}>{formatValue("temp", r.temp)}</td>
                  </>
                ) : (
                  <td colSpan={5} className="num muted">
                    waiting for monitor
                  </td>
                )}
                <td className="trend">
                  <Sparkline values={(history[p.id] ?? []).slice(-60).map((x) => x.hr)} />
                </td>
                <td className={`status s-${worst}`}>
                  {r ? STATUS_TEXT[worst] : "—"}
                  {pending > 0 && <span className="pending">{pending} open</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
