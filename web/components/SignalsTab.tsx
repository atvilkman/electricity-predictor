"use client";
import { useEffect, useState } from "react";
import { useLanguage } from "@/lib/i18n";

type SignalsSnapshot = {
  generated_at: string;
  wind: { value_ms: number | null; baseline_ms: number | null };
  solar: { value_wm2: number | null; baseline_wm2: number | null };
  demand: { value_c: number | null; baseline_c: number | null };
  hydro: { value_mm: number | null; baseline_mm: number | null; as_of?: string };
  transmission: Record<string, number | null>;
  nuclear: { value_mw: number | null; pct_of_capacity: number | null };
};

type Arrow = "up" | "down" | "flat";

function ArrowIcon({ dir }: { dir: Arrow }) {
  const color = dir === "up" ? "#10b981" : dir === "down" ? "#ef4444" : "#eab308";
  const rotate = dir === "up" ? 0 : dir === "down" ? 180 : 90;
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ transform: `rotate(${rotate}deg)` }}>
      <path d="M12 20V4M12 4L4 12M12 4L20 12" stroke={color} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function pctDiff(value: number | null, baseline: number | null): number | null {
  if (value === null || baseline === null || baseline === 0) return null;
  return ((value - baseline) / baseline) * 100;
}

function Tile({
  title, value, unit, comparisonLabel, arrow, shows, notShows, noData,
}: {
  title: string; value: string; unit: string; comparisonLabel: string;
  arrow: Arrow; shows: string; notShows: string; noData: string;
}) {
  const hasData = value !== "—";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between mb-2">
        <div className="text-xs uppercase tracking-wide text-gray-500">{title}</div>
        {hasData && (
          <div
            className="rounded-full p-2"
            style={{
              backgroundColor:
                arrow === "up" ? "rgba(16,185,129,0.12)" :
                arrow === "down" ? "rgba(239,68,68,0.12)" :
                "rgba(234,179,8,0.12)",
            }}
          >
            <ArrowIcon dir={arrow} />
          </div>
        )}
      </div>
      {hasData ? (
        <>
          <div className="text-2xl font-semibold text-gray-900">
            {value} <span className="text-sm font-normal text-gray-400">{unit}</span>
          </div>
          <div className="text-xs text-gray-400 mt-1">{comparisonLabel}</div>
        </>
      ) : (
        <div className="text-sm text-gray-400">{noData}</div>
      )}
      <div className="mt-3 pt-3 border-t border-gray-100 space-y-1">
        <p className="text-xs text-gray-500">{shows}</p>
        <p className="text-xs text-gray-400">{notShows}</p>
      </div>
    </div>
  );
}

export default function SignalsTab() {
  const { t } = useLanguage();
  const [snap, setSnap] = useState<SignalsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const base = process.env.NODE_ENV === "production" ? "/electricity-predictor" : "";
    fetch(`${base}/data/signals_snapshot.json`, { cache: "no-store" })
      .then(r => r.json())
      .then(setSnap)
      .catch(e => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-600 text-sm">Failed to load signals: {error}</p>;
  if (!snap) return <p className="text-gray-500 text-sm">Loading…</p>;

  const windDiff = pctDiff(snap.wind.value_ms, snap.wind.baseline_ms);
  const windArrow: Arrow = windDiff === null ? "flat" : windDiff > 5 ? "up" : windDiff < -5 ? "down" : "flat";

  const solarDiff = pctDiff(snap.solar.value_wm2, snap.solar.baseline_wm2);
  const solarArrow: Arrow = solarDiff === null ? "flat" : solarDiff > 5 ? "up" : solarDiff < -5 ? "down" : "flat";

  const hydroDiff = pctDiff(snap.hydro.value_mm, snap.hydro.baseline_mm);
  const hydroArrow: Arrow = (snap.hydro.value_mm === 0 && snap.hydro.baseline_mm === 0) ? "flat"
    : hydroDiff === null ? "flat" : hydroDiff > 5 ? "up" : hydroDiff < -5 ? "down" : "flat";

  const demandDiff = snap.demand.value_c !== null && snap.demand.baseline_c !== null
    ? snap.demand.value_c - snap.demand.baseline_c : null;
  const demandArrowFinal: Arrow = demandDiff === null ? "flat"
    : Math.abs(demandDiff) <= 2 ? "flat" : "down";

  const nuclearArrow: Arrow = snap.nuclear.pct_of_capacity === null ? "flat"
    : snap.nuclear.pct_of_capacity >= 90 ? "up" : snap.nuclear.pct_of_capacity < 75 ? "down" : "flat";

  const transmissionValues = Object.values(snap.transmission).filter((v): v is number => v !== null);
  const transmissionAvg = transmissionValues.length
    ? transmissionValues.reduce((a, b) => a + b, 0) / transmissionValues.length : null;
  const transmissionArrow: Arrow = transmissionAvg === null ? "flat"
    : transmissionAvg > 1400 ? "up" : transmissionAvg < 800 ? "down" : "flat";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{t("signalsTitle")}</h2>
        <p className="text-sm text-gray-500">{t("signalsIntro")}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Tile
          title={t("signalWindTitle")}
          value={snap.wind.value_ms !== null ? snap.wind.value_ms.toFixed(1) : "—"}
          unit="m/s"
          comparisonLabel={windDiff !== null ? `${windDiff > 0 ? "+" : ""}${windDiff.toFixed(0)}% ${t("signalVsBaseline")}` : ""}
          arrow={windArrow}
          shows={t("signalWindShows")} notShows={t("signalWindNotShows")} noData={t("signalNoData")}
        />
        <Tile
          title={t("signalSolarTitle")}
          value={snap.solar.value_wm2 !== null ? snap.solar.value_wm2.toFixed(0) : "—"}
          unit="W/m²"
          comparisonLabel={solarDiff !== null ? `${solarDiff > 0 ? "+" : ""}${solarDiff.toFixed(0)}% ${t("signalVsBaseline")}` : ""}
          arrow={solarArrow}
          shows={t("signalSolarShows")} notShows={t("signalSolarNotShows")} noData={t("signalNoData")}
        />
        <Tile
          title={t("signalHydroTitle")}
          value={snap.hydro.value_mm !== null ? snap.hydro.value_mm.toFixed(1) : "—"}
          unit="mm SWE"
          comparisonLabel={hydroDiff !== null ? `${hydroDiff > 0 ? "+" : ""}${hydroDiff.toFixed(0)}% ${t("signalVsSeasonal")}` : ""}
          arrow={hydroArrow}
          shows={t("signalHydroShows")} notShows={t("signalHydroNotShows")} noData={t("signalNoData")}
        />
        <Tile
          title={t("signalNuclearTitle")}
          value={snap.nuclear.pct_of_capacity !== null ? snap.nuclear.pct_of_capacity.toFixed(1) : "—"}
          unit="%"
          comparisonLabel={snap.nuclear.value_mw !== null ? `${snap.nuclear.value_mw.toFixed(0)} MW ${t("signalOfCapacity")}` : ""}
          arrow={nuclearArrow}
          shows={t("signalNuclearShows")} notShows={t("signalNuclearNotShows")} noData={t("signalNoData")}
        />
        <Tile
          title={t("signalTransmissionTitle")}
          value={transmissionAvg !== null ? transmissionAvg.toFixed(0) : "—"}
          unit="MW avg"
          comparisonLabel=""
          arrow={transmissionArrow}
          shows={t("signalTransmissionShows")} notShows={t("signalTransmissionNotShows")} noData={t("signalNoData")}
        />
        <Tile
          title={t("signalDemandTitle")}
          value={snap.demand.value_c !== null ? snap.demand.value_c.toFixed(1) : "—"}
          unit="°C"
          comparisonLabel={demandDiff !== null ? `${demandDiff > 0 ? "+" : ""}${demandDiff.toFixed(1)}°C ${t("signalVsBaseline")}` : ""}
          arrow={demandArrowFinal}
          shows={t("signalDemandShows")} notShows={t("signalDemandNotShows")} noData={t("signalNoData")}
        />
      </div>
    </div>
  );
}
