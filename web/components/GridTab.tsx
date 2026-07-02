"use client";
import { useEffect, useState } from "react";
import {
  ComposedChart, AreaChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { loadGridSnapshot, filterByDays, type GridSnapshot } from "@/lib/gridData";

type RangeOption = 7 | 30 | 180;

const FUEL_COLORS: Record<string, string> = {
  "Nuclear": "#7c3aed",
  "Wind Onshore": "#10b981",
  "Wind Offshore": "#059669",
  "Hydro Water Reservoir": "#3b82f6",
  "Hydro Run-of-river and poundage": "#60a5fa",
  "Fossil Gas": "#f59e0b",
  "Fossil Hard coal": "#78716c",
  "Biomass": "#84cc16",
  "Solar": "#eab308",
  "Other": "#9ca3af",
};

function fmtAxis(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    timeZone: "Europe/Helsinki", day: "2-digit", month: "short",
  });
}

function RangeSelector({ value, onChange }: { value: RangeOption; onChange: (v: RangeOption) => void }) {
  return (
    <div className="flex gap-2">
      {([7, 30, 180] as RangeOption[]).map(opt => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`px-3 py-1 text-sm rounded-full border transition-colors ${
            value === opt
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
          }`}
        >
          {opt}d
        </button>
      ))}
    </div>
  );
}

export default function GridTab() {
  const [snap, setSnap] = useState<GridSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadRange, setLoadRange] = useState<RangeOption>(7);
  const [genRange, setGenRange] = useState<RangeOption>(7);
  const [flowRange, setFlowRange] = useState<RangeOption>(7);

  useEffect(() => {
    loadGridSnapshot().then(setSnap).catch(e => setError(String(e)));
  }, []);

  if (error) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <p className="text-red-600 text-sm">Failed to load grid data: {error}</p>
      </section>
    );
  }
  if (!snap) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <p className="text-gray-500 text-sm">Loading grid data…</p>
      </section>
    );
  }

  const loadData = filterByDays(snap.load, loadRange);

  const genFiltered = filterByDays(snap.generation, genRange);
  const genByTime = new Map<string, Record<string, number | string>>();
  for (const row of genFiltered) {
    if (!genByTime.has(row.t)) genByTime.set(row.t, { t: row.t });
    genByTime.get(row.t)![row.fuel] = row.mw;
  }
  const genData = Array.from(genByTime.values()).sort((a, b) =>
    new Date(a.t as string).getTime() - new Date(b.t as string).getTime()
  );
  const fuelTypes = Array.from(new Set(genFiltered.map(r => r.fuel)));

  const flowFiltered = filterByDays(snap.crossborder, flowRange);
  const flowByTime = new Map<string, Record<string, number | string>>();
  for (const row of flowFiltered) {
    if (!flowByTime.has(row.t)) flowByTime.set(row.t, { t: row.t });
    flowByTime.get(row.t)![row.border] = row.mw;
  }
  const flowData = Array.from(flowByTime.values()).sort((a, b) =>
    new Date(a.t as string).getTime() - new Date(b.t as string).getTime()
  );
  const borders = Array.from(new Set(flowFiltered.map(r => r.border)));
  const borderColors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Actual Load</h2>
          <RangeSelector value={loadRange} onChange={setLoadRange} />
        </div>
        <div className="w-full h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={loadData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="t" tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} label={{ value: "MW", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }} />
              <Tooltip labelFormatter={(l) => fmtAxis(String(l))} formatter={(v) => [typeof v === "number" ? `${v.toFixed(0)} MW` : String(v ?? ""), "Load"]} />
              <Area type="monotone" dataKey="mw" stroke="#1f77b4" fill="#1f77b4" fillOpacity={0.15} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Generation by Fuel Type</h2>
          <RangeSelector value={genRange} onChange={setGenRange} />
        </div>
        <div className="w-full h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={genData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="t" tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} label={{ value: "MW", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }} />
              <Tooltip labelFormatter={(l) => fmtAxis(String(l))} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {fuelTypes.map(fuel => (
                <Area
                  key={fuel} type="monotone" dataKey={fuel} stackId="1"
                  stroke={FUEL_COLORS[fuel] ?? "#9ca3af"} fill={FUEL_COLORS[fuel] ?? "#9ca3af"}
                  fillOpacity={0.7}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {flowData.length > 0 ? (
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Cross-Border Flows</h2>
            <RangeSelector value={flowRange} onChange={setFlowRange} />
          </div>
          <div className="w-full h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={flowData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="t" tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: "#6b7280" }} />
                <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} label={{ value: "MW", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }} />
                <Tooltip labelFormatter={(l) => fmtAxis(String(l))} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {borders.map((border, i) => (
                  <Line
                    key={border} type="monotone" dataKey={border}
                    stroke={borderColors[i % borderColors.length]} dot={false} strokeWidth={1.5}
                  />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-3 text-xs text-gray-400">
            Positive-direction pairs (e.g. SE1→FI and FI→SE1) show import/export separately.
          </p>
        </section>
      ) : null}
    </div>
  );
}
