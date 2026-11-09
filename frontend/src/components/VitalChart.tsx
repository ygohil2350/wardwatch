import { classify, formatValue, type Band, type Bands, type Metric, type Reading } from "../api";

const W = 640;
const H = 96;
const WINDOW_MS = 10 * 60 * 1000;

type Props = {
  metric: Metric;
  label: string;
  unit: string;
  domain: [number, number];
  readings: Reading[];
  bands: Bands | null;
  now: number;
};

// Shaded zones for the warning and critical ranges, drawn from the server's bands.
function zones(band: Band | undefined, [lo, hi]: [number, number]) {
  if (!band) return [];
  const out: { from: number; to: number; level: "warning" | "critical" }[] = [];
  if (band.critical_low !== null) out.push({ from: lo, to: band.critical_low, level: "critical" });
  if (band.warning_low !== null) out.push({ from: band.critical_low ?? lo, to: band.warning_low, level: "warning" });
  if (band.warning_high !== null) out.push({ from: band.warning_high, to: band.critical_high ?? hi, level: "warning" });
  if (band.critical_high !== null) out.push({ from: band.critical_high, to: hi, level: "critical" });
  return out.filter((z) => z.to > lo && z.from < hi);
}

export default function VitalChart({ metric, label, unit, domain, readings, bands, now }: Props) {
  const [lo, hi] = domain;
  const y = (v: number) => H - ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * H;
  const x = (iso: string) => W - ((now - new Date(iso).getTime()) / WINDOW_MS) * W;
  const visible = readings.filter((r) => now - new Date(r.taken_at).getTime() <= WINDOW_MS);
  const line = (key: keyof Reading) =>
    visible.map((r) => `${x(r.taken_at).toFixed(1)},${y(r[key] as number).toFixed(1)}`).join(" ");
  const last = visible[visible.length - 1];
  const level = last ? classify(bands, metric, last[metric]) : "normal";

  return (
    <figure className="chart">
      <figcaption>
        <span>{label}</span>
        <span className={`chart-now v-${level}`}>
          {last ? (metric === "sys" ? `${last.sys}/${last.dia}` : formatValue(metric, last[metric])) : "–"}
          <small> {unit}</small>
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`${label}, last 10 minutes`}>
        {zones(bands?.[metric], domain).map((z) => (
          <rect key={`${z.level}-${z.from}`} className={`zone z-${z.level}`} x={0} width={W} y={y(z.to)} height={y(z.from) - y(z.to)} />
        ))}
        {metric === "sys" && visible.length > 1 && <polyline className="line line-dia" points={line("dia")} />}
        {visible.length > 1 && <polyline className="line" points={line(metric)} />}
      </svg>
      <div className="chart-axis" aria-hidden="true">
        <span>10 min ago</span>
        <span>5</span>
        <span>now</span>
      </div>
    </figure>
  );
}
