export default function Sparkline({ values, width = 96, height = 24 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const min = Math.min(...values) - 2;
  const max = Math.max(...values) + 2;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / (max - min)) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="spark">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
    </svg>
  );
}
