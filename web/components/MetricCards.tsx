import type { Snapshot } from "@/lib/data";

export default function MetricCards({ snap }: { snap: Snapshot }) {
  const prices = snap.known.map(r => r.p);
  if (prices.length === 0) return null;
  const cheapest = Math.min(...prices);
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
  const expensive = Math.max(...prices);
  const now = Date.now();
  const currentKnown = [...snap.known].reverse().find(r => new Date(r.t).getTime() <= now);
  const current = currentKnown;

  const Card = ({ label, value, hint }: { label: string; value: string; hint?: string }) => (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-gray-900">{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-400">{hint}</div>}
    </div>
  );

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {current && <Card label="Current price" value={`${current.p.toFixed(2)} snt/kWh`} hint="Latest known hour" />}
      <Card label="Cheapest" value={`${cheapest.toFixed(2)} snt/kWh`} hint="Current 36h window" />
      <Card label="Average" value={`${avg.toFixed(2)} snt/kWh`} hint="Current 36h window" />
      <Card label="Most expensive" value={`${expensive.toFixed(2)} snt/kWh`} hint="Current 36h window" />
    </div>
  );
}
