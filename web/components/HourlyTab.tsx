"use client";
import { useEffect, useState } from "react";
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { useLanguage } from "@/lib/i18n";

type HourlyPoint = { t: string; p: number; horizon_h: number };
type HourlySnapshot = { generated_at: string; hourly: HourlyPoint[] };

function fmtAxis(v: number): string {
  return new Date(v).toLocaleString("en-GB", {
    timeZone: "Europe/Helsinki", day: "2-digit", month: "short", hour: "2-digit",
  });
}
function fmtTooltip(v: number): string {
  return new Date(v).toLocaleString("en-GB", {
    timeZone: "Europe/Helsinki", weekday: "short", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function HourlyTab() {
  const { t } = useLanguage();
  const [snap, setSnap] = useState<HourlySnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const base = process.env.NODE_ENV === "production" ? "/electricity-predictor" : "";
    fetch(`${base}/data/hourly_snapshot.json`, { cache: "no-store" })
      .then(r => r.json())
      .then(setSnap)
      .catch(e => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-600 text-sm">Failed to load hourly forecast: {error}</p>;
  if (!snap) return <p className="text-gray-500 text-sm">Loading…</p>;
  if (snap.hourly.length === 0) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
          <p className="text-sm text-blue-900">{t("hourlyEmpty")}</p>
        </div>
      </section>
    );
  }

  const data = snap.hourly.map(r => ({ t: new Date(r.t).getTime(), p: r.p, horizon_h: r.horizon_h }));
  const now = Date.now();

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">{t("hourlyTitle")}</h2>
      <p className="text-xs text-gray-400 mb-4">{t("hourlyNote")}</p>
      <div className="w-full h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
                   tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: "#6b7280" }} />
            <YAxis tick={{ fontSize: 11, fill: "#6b7280" }}
                   label={{ value: "snt/kWh", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }} />
            <Tooltip labelFormatter={(v) => fmtTooltip(v as number)}
                     formatter={(v) => [typeof v === "number" ? `${v.toFixed(2)} snt/kWh` : String(v ?? ""), "Predicted"]} />
            <ReferenceLine x={now} stroke="#374151" strokeDasharray="2 2"
                           label={{ value: "Now", position: "top", fontSize: 12 }} />
            <Line type="monotone" dataKey="p" stroke="#1f77b4" strokeWidth={2} dot={false}
                  isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs text-gray-400">{t("priceVarianceNote")}</p>
    </section>
  );
}
