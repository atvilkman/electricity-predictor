"use client";
import { useEffect, useState } from "react";
import ForecastChart from "@/components/ForecastChart";
import MetricCards from "@/components/MetricCards";
import Tabs from "@/components/Tabs";
import EmptyTab from "@/components/EmptyTab";
import { loadSnapshot, type Snapshot } from "@/lib/data";

export default function Home() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSnapshot().then(setSnap).catch(e => setError(String(e)));
  }, []);

  if (error) {
    return (
      <main className="mx-auto max-w-6xl p-8">
        <p className="text-red-600">Failed to load snapshot: {error}</p>
      </main>
    );
  }
  if (!snap) {
    return (
      <main className="mx-auto max-w-6xl p-8">
        <p className="text-gray-500">Loading…</p>
      </main>
    );
  }

  const generated = new Date(snap.generated_at).toLocaleString("en-GB", {
    timeZone: "Europe/Helsinki", weekday: "short", day: "2-digit",
    month: "short", hour: "2-digit", minute: "2-digit",
  });

  const forecastTab = (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Forecast</h2>
        <ForecastChart snap={snap} />
        <p className="mt-3 text-xs text-gray-400">
          Shaded band = typical historical error for that horizon (mean absolute error from backtesting).
        </p>
      </section>
      <MetricCards snap={snap} />
    </div>
  );

  return (
    <main className="mx-auto max-w-6xl px-6 py-10 space-y-8">
      <header className="space-y-2">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Finnish Electricity Spot Price
        </h1>
        <p className="text-gray-500">
          Rolling forecast: known ~36h + predicted 5 days.
        </p>
        <p className="text-xs text-gray-400">
          Generated {generated} · Prices are raw wholesale spot (excl. ALV / VAT and retailer margin).
        </p>
      </header>

      <Tabs tabs={[
        { id: "forecast", label: "Forecast", content: forecastTab },
        { id: "vs-actual", label: "Forecast vs Actual", content:
          <EmptyTab
            title="Frozen forecasts vs what actually happened"
            message="Not enough history yet. This view fills in as daily forecasts graduate into known actuals — check back after a few days of automated runs."
          /> },
        { id: "accuracy", label: "Accuracy", content:
          <EmptyTab
            title="Accuracy: model vs naive-week baseline, by horizon"
            message="No scored predictions yet. Accuracy fills in once daily forecasts graduate into known actuals — needs several days of automated runs."
          /> },
      ]} />
    </main>
  );
}
