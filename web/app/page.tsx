"use client";
import { useEffect, useState } from "react";
import ForecastChart from "@/components/ForecastChart";
import MetricCards from "@/components/MetricCards";
import Tabs from "@/components/Tabs";
import EmptyTab from "@/components/EmptyTab";
import GridTab from "@/components/GridTab";
import HourlyTab from "@/components/HourlyTab";
import AboutTab from "@/components/AboutTab";
import { loadSnapshot, type Snapshot } from "@/lib/data";
import { useLanguage } from "@/lib/i18n";

export default function Home() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { lang, setLang, t } = useLanguage();

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
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("tabForecast")}</h2>
        <ForecastChart snap={snap} />
      </section>
      <MetricCards snap={snap} />
    </div>
  );

  return (
    <main className="mx-auto max-w-6xl px-6 py-10 space-y-8">
      <header className="space-y-2">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          {t("appTitle")}
        </h1>
        <p className="text-gray-500">
          {t("appSubtitle")}
        </p>
        <p className="text-xs text-gray-400">
          {t("generatedPrefix")} {generated} · {t("priceNote")}
        </p>
        <div className="flex gap-2 pt-2">
          <button
            onClick={() => setLang("en")}
            className={`px-3 py-1 text-sm rounded-full border ${lang === "en" ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-600 border-gray-300"}`}
          >
            EN
          </button>
          <button
            onClick={() => setLang("fi")}
            className={`px-3 py-1 text-sm rounded-full border ${lang === "fi" ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-600 border-gray-300"}`}
          >
            FI
          </button>
        </div>
      </header>

      <Tabs tabs={[
        { id: "forecast", label: t("tabForecast"), content: forecastTab },
        { id: "hourly", label: t("tabHourly"), content: <HourlyTab /> },
        { id: "vs-actual", label: t("tabVsActual"), content:
          <EmptyTab title={t("vsActualTitle")} message={t("vsActualEmpty")} /> },
        { id: "accuracy", label: t("tabAccuracy"), content:
          <EmptyTab title={t("accuracyTitle")} message={t("accuracyEmpty")} /> },
        { id: "grid", label: t("tabGrid"), content: <GridTab /> },
        { id: "about", label: t("tabAbout"), content: <AboutTab /> },
      ]} />
      <footer className="mt-12 pb-8 text-center text-xs text-gray-400">
        {t("footerPoweredBy")}
      </footer>
    </main>
  );
}
