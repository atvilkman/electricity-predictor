"use client";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useLanguage } from "@/lib/i18n";
import type { LiveAccRow, ValAccRow } from "@/lib/data";

export default function AccuracyTab({ live, validation }: { live: LiveAccRow[]; validation: ValAccRow[] }) {
  const { t } = useLanguage();

  return (
    <div className="space-y-6">
      {/* Validation accuracy — always available from training */}
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{t("accuracyValidationTitle")}</h2>
        <p className="text-sm text-gray-500 mb-5">{t("accuracyValidationCaption")}</p>

        {validation.length === 0 ? (
          <p className="text-sm text-gray-400">{t("accuracyEmpty")}</p>
        ) : (
          <>
            <div className="w-full h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={validation}
                  margin={{ top: 10, right: 20, left: 10, bottom: 5 }}
                  barCategoryGap="30%"
                  barGap={4}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="label" tick={{ fontSize: 13, fill: "#4b5563" }} stroke="#9ca3af" />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#6b7280" }}
                    stroke="#9ca3af"
                    label={{ value: "snt/kWh", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }}
                  />
                  <Tooltip
                    formatter={(v) => [typeof v === "number" ? `${v.toFixed(3)} snt/kWh` : String(v ?? ""), ""]}
                  />
                  <Legend wrapperStyle={{ fontSize: 13 }} />
                  <Bar dataKey="model_mae" name={t("accuracyModel")} fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="naive_mae" name={t("accuracyNaive")} fill="#d1d5db" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Per-horizon beats-naive summary */}
            <div className="mt-5 grid grid-cols-2 sm:grid-cols-5 gap-3">
              {validation.map(r => (
                <div key={r.horizon_h} className="rounded-xl border border-gray-100 p-3 text-center">
                  <div className="text-sm font-semibold text-gray-700">{r.label}</div>
                  <div className="mt-1 text-lg font-bold" style={{ color: r.beats_naive ? "#10b981" : "#ef4444" }}>
                    {r.model_mae.toFixed(2)}
                  </div>
                  <div className="text-xs text-gray-400">snt/kWh</div>
                  <div className={`mt-1 text-xs font-medium ${r.beats_naive ? "text-green-600" : "text-red-500"}`}>
                    {r.beats_naive ? "✓" : "✗"} {t("accuracyBeatsNaive")}
                  </div>
                  <div className="text-xs text-gray-300 mt-0.5">{r.n_val} samples</div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      {/* Live accuracy — grows over time */}
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{t("accuracyLiveTitle")}</h2>
        <p className="text-sm text-gray-500 mb-4">{t("accuracyLiveCaption")}</p>

        {live.length === 0 ? (
          <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
            <p className="text-sm text-blue-900">{t("accuracyEmpty")}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left pb-2 pr-6 text-xs font-medium text-gray-500 uppercase tracking-wide">Horizon</th>
                  <th className="text-right pb-2 pr-6 text-xs font-medium text-gray-500 uppercase tracking-wide">MAE (snt/kWh)</th>
                  <th className="text-right pb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">n</th>
                </tr>
              </thead>
              <tbody>
                {live.map(r => (
                  <tr key={r.horizon_h} className="border-b border-gray-50">
                    <td className="py-2.5 pr-6 font-medium text-gray-700">{r.label}</td>
                    <td className="py-2.5 pr-6 text-right tabular-nums text-gray-700">{r.mae.toFixed(3)}</td>
                    <td className="py-2.5 text-right text-gray-400">{r.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
