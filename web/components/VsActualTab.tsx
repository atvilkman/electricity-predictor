"use client";
import { useLanguage } from "@/lib/i18n";
import type { VsActualRecord } from "@/lib/data";

const HORIZON_COLORS: Record<number, string> = {
  24: "#3b82f6",
  48: "#10b981",
  72: "#f59e0b",
  96: "#8b5cf6",
  120: "#ef4444",
};

export default function VsActualTab({ records }: { records: VsActualRecord[] }) {
  const { t, lang } = useLanguage();
  const locale = lang === "fi" ? "fi-FI" : "en-GB";

  if (records.length === 0) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">{t("vsActualTitle")}</h2>
        <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
          <p className="text-sm text-blue-900">{t("vsActualEmpty")}</p>
        </div>
      </section>
    );
  }

  const sorted = [...records].sort(
    (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime() || a.horizon_h - b.horizon_h
  );

  const horizonsPresent = Array.from(new Set(sorted.map(r => r.horizon_h))).sort((a, b) => a - b);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{t("vsActualTitle")}</h2>
        <p className="text-sm text-gray-500 mb-5">{t("vsActualCaption")}</p>

        {/* Horizon legend */}
        <div className="flex gap-4 flex-wrap mb-5">
          {horizonsPresent.map(h => (
            <div key={h} className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: HORIZON_COLORS[h] ?? "#9ca3af" }} />
              N+{h / 24}
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left pb-2 pr-6 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("vsActualDate")}</th>
                <th className="text-left pb-2 pr-6 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("vsActualHorizon")}</th>
                <th className="text-right pb-2 pr-6 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("vsActualPredicted")}</th>
                <th className="text-right pb-2 pr-6 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("vsActualActual")}</th>
                <th className="text-right pb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("vsActualError")}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => {
                const err = r.predicted - r.actual;
                const absErr = Math.abs(err);
                const errColor = absErr <= 0.5 ? "#10b981" : absErr <= 2 ? "#f59e0b" : "#ef4444";
                const date = new Date(r.t).toLocaleString(locale, {
                  timeZone: "Europe/Helsinki",
                  weekday: "short", day: "2-digit", month: "short", hour: "2-digit",
                });
                const madeAt = new Date(r.made_at).toLocaleString(locale, {
                  timeZone: "Europe/Helsinki", day: "2-digit", month: "short", hour: "2-digit",
                });
                return (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2.5 pr-6 text-gray-700">
                      <div>{date}</div>
                      <div className="text-xs text-gray-400">made {madeAt}</div>
                    </td>
                    <td className="py-2.5 pr-6">
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-white"
                        style={{ backgroundColor: HORIZON_COLORS[r.horizon_h] ?? "#9ca3af" }}
                      >
                        N+{r.horizon_h / 24}
                      </span>
                    </td>
                    <td className="py-2.5 pr-6 text-right tabular-nums text-gray-700">
                      {r.predicted.toFixed(2)} <span className="text-gray-400 text-xs">snt</span>
                    </td>
                    <td className="py-2.5 pr-6 text-right tabular-nums text-gray-700">
                      {r.actual.toFixed(2)} <span className="text-gray-400 text-xs">snt</span>
                    </td>
                    <td className="py-2.5 text-right tabular-nums font-medium" style={{ color: errColor }}>
                      {err > 0 ? "+" : ""}{err.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-gray-400">{t("priceVarianceNote")}</p>
      </section>
    </div>
  );
}
