"use client";
import { useEffect, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { loadGridSnapshot, filterByDays, type GridSnapshot } from "@/lib/gridData";
import { useLanguage, translateFuel } from "@/lib/i18n";

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

const BORDER_COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"];

const FUEL_CATEGORY: Record<string, "renewable" | "nuclear" | "fossil"> = {
  "Wind Onshore": "renewable",
  "Wind Offshore": "renewable",
  "Hydro Water Reservoir": "renewable",
  "Hydro Run-of-river and poundage": "renewable",
  "Hydro Pumped Storage": "renewable",
  "Solar": "renewable",
  "Biomass": "renewable",
  "Other renewable": "renewable",
  "Waste": "renewable",
  "Nuclear": "nuclear",
  "Fossil Gas": "fossil",
  "Fossil Hard coal": "fossil",
  "Fossil Oil": "fossil",
  "Fossil Peat": "fossil",
  "Fossil Brown coal/Lignite": "fossil",
  "Energy storage": "fossil",
  "Other": "fossil",
};

const EMISSION_FACTORS_G_PER_KWH: Record<string, number> = {
  "Nuclear": 12,
  "Wind Onshore": 11,
  "Wind Offshore": 12,
  "Hydro Water Reservoir": 24,
  "Hydro Run-of-river and poundage": 24,
  "Hydro Pumped Storage": 24,
  "Solar": 45,
  "Biomass": 230,
  "Other renewable": 50,
  "Waste": 150,
  "Fossil Gas": 490,
  "Fossil Hard coal": 820,
  "Fossil Oil": 650,
  "Fossil Peat": 900,
  "Fossil Brown coal/Lignite": 1000,
  "Energy storage": 0,
  "Other": 400,
};

function computeSustainabilityShares(
  generation: { t: string; fuel: string; mw: number }[],
  days: number
): { renewable: number; nuclear: number; fossil: number } {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const filtered = generation.filter(r => new Date(r.t).getTime() >= cutoff);
  const totals = { renewable: 0, nuclear: 0, fossil: 0 };
  let grandTotal = 0;
  for (const row of filtered) {
    const cat = FUEL_CATEGORY[row.fuel] ?? "fossil";
    if (row.mw > 0) { totals[cat] += row.mw; grandTotal += row.mw; }
  }
  if (grandTotal === 0) return { renewable: 0, nuclear: 0, fossil: 0 };
  return {
    renewable: (totals.renewable / grandTotal) * 100,
    nuclear: (totals.nuclear / grandTotal) * 100,
    fossil: (totals.fossil / grandTotal) * 100,
  };
}

function computeCarbonIntensity(
  generation: { t: string; fuel: string; mw: number }[],
  days: number
): number {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const filtered = generation.filter(r => new Date(r.t).getTime() >= cutoff);
  let weightedSum = 0;
  let totalMw = 0;
  for (const row of filtered) {
    if (row.mw > 0) {
      const factor = EMISSION_FACTORS_G_PER_KWH[row.fuel] ?? 400;
      weightedSum += row.mw * factor;
      totalMw += row.mw;
    }
  }
  return totalMw === 0 ? 0 : weightedSum / totalMw;
}

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

function SustainabilityCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold" style={{ color }}>{value.toFixed(1)}%</div>
    </div>
  );
}

function CarbonCard({ label, value }: { label: string; value: number }) {
  const color = value < 100 ? "#10b981" : value < 300 ? "#f59e0b" : "#ef4444";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold" style={{ color }}>{value.toFixed(0)}</div>
      <div className="text-xs text-gray-400">gCO₂/kWh</div>
    </div>
  );
}

function SeriesFilterDropdown({
  options, selected, onToggle, onSelectAll, onClearAll, colors, isOpen, setIsOpen, label,
  getLabel = (opt: string) => opt,
  selectAllLabel = "Select all",
  clearAllLabel = "Clear all",
}: {
  options: string[];
  selected: Set<string>;
  onToggle: (opt: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  colors: Record<string, string>;
  isOpen: boolean;
  setIsOpen: (v: boolean) => void;
  label: string;
  getLabel?: (opt: string) => string;
  selectAllLabel?: string;
  clearAllLabel?: string;
}) {
  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 bg-white text-gray-700 hover:border-gray-400 flex items-center gap-2"
      >
        {label} ({selected.size}/{options.length})
        <span className="text-gray-400">{isOpen ? "▲" : "▼"}</span>
      </button>
      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 mt-2 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-20 p-3">
            <div className="flex gap-2 mb-2 pb-2 border-b border-gray-100">
              <button onClick={onSelectAll} className="text-xs text-blue-600 hover:underline">{selectAllLabel}</button>
              <button onClick={onClearAll} className="text-xs text-blue-600 hover:underline">{clearAllLabel}</button>
            </div>
            <div className="flex flex-col gap-1.5 max-h-[280px] overflow-y-auto">
              {options.map(opt => (
                <label key={opt} className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.has(opt)}
                    onChange={() => onToggle(opt)}
                    className="rounded border-gray-300"
                  />
                  <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: colors[opt] ?? "#9ca3af" }} />
                  <span className="truncate">{getLabel(opt)}</span>
                </label>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function GridTab() {
  const { t, lang } = useLanguage();
  const [snap, setSnap] = useState<GridSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadRange, setLoadRange] = useState<RangeOption>(7);
  const [genRange, setGenRange] = useState<RangeOption>(7);
  const [flowRange, setFlowRange] = useState<RangeOption>(7);
  const [selectedFuels, setSelectedFuels] = useState<Set<string>>(new Set());
  const [selectedBorders, setSelectedBorders] = useState<Set<string>>(new Set());
  const [genFilterOpen, setGenFilterOpen] = useState(false);
  const [flowFilterOpen, setFlowFilterOpen] = useState(false);

  useEffect(() => {
    loadGridSnapshot().then(setSnap).catch(e => setError(String(e)));
  }, []);

  // Hoisted before conditional returns so hooks are called unconditionally.
  const genFiltered = snap ? filterByDays(snap.generation, genRange) : [];
  const fuelTypes = Array.from(new Set(genFiltered.map(r => r.fuel)));
  const flowFiltered = snap ? filterByDays(snap.crossborder, flowRange) : [];
  const borders = Array.from(new Set(flowFiltered.map(r => r.border)));

  useEffect(() => {
    if (fuelTypes.length > 0 && selectedFuels.size === 0) {
      setSelectedFuels(new Set(fuelTypes));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fuelTypes.join(",")]);

  useEffect(() => {
    if (borders.length > 0 && selectedBorders.size === 0) {
      setSelectedBorders(new Set(borders));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [borders.join(",")]);

  const toggleFuel = (fuel: string) => {
    setSelectedFuels(prev => {
      const next = new Set(prev);
      next.has(fuel) ? next.delete(fuel) : next.add(fuel);
      return next;
    });
  };
  const toggleBorder = (border: string) => {
    setSelectedBorders(prev => {
      const next = new Set(prev);
      next.has(border) ? next.delete(border) : next.add(border);
      return next;
    });
  };

  const selectAllFuels = () => setSelectedFuels(new Set(fuelTypes));
  const clearAllFuels = () => setSelectedFuels(new Set());
  const selectAllBorders = () => setSelectedBorders(new Set(borders));
  const clearAllBorders = () => setSelectedBorders(new Set());

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

  const genByTime = new Map<string, Record<string, number | string>>();
  for (const row of genFiltered) {
    if (!genByTime.has(row.t)) genByTime.set(row.t, { t: row.t });
    genByTime.get(row.t)![row.fuel] = row.mw;
  }
  const genData = Array.from(genByTime.values()).sort((a, b) =>
    new Date(a.t as string).getTime() - new Date(b.t as string).getTime()
  );

  const flowByTime = new Map<string, Record<string, number | string>>();
  for (const row of flowFiltered) {
    if (!flowByTime.has(row.t)) flowByTime.set(row.t, { t: row.t });
    flowByTime.get(row.t)![row.border] = row.mw;
  }
  const flowData = Array.from(flowByTime.values()).sort((a, b) =>
    new Date(a.t as string).getTime() - new Date(b.t as string).getTime()
  );

  const shares7d = computeSustainabilityShares(snap.generation, 7);
  const shares30d = computeSustainabilityShares(snap.generation, 30);
  const shares180d = computeSustainabilityShares(snap.generation, 180);

  const co2_7d = computeCarbonIntensity(snap.generation, 7);
  const co2_30d = computeCarbonIntensity(snap.generation, 30);
  const co2_180d = computeCarbonIntensity(snap.generation, 180);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">{t("gridLoadTitle")}</h2>
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
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("gridSustainabilityTitle")}</h2>

        <div className="mb-3 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("gridLast7")}</div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
          <SustainabilityCard label={t("gridRenewable")} value={shares7d.renewable} color="#10b981" />
          <SustainabilityCard label={t("gridNuclear")} value={shares7d.nuclear} color="#7c3aed" />
          <SustainabilityCard label={t("gridFossil")} value={shares7d.fossil} color="#78716c" />
          <CarbonCard label={t("gridCarbonIntensity")} value={co2_7d} />
        </div>

        <div className="mb-3 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("gridLast30")}</div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
          <SustainabilityCard label={t("gridRenewable")} value={shares30d.renewable} color="#10b981" />
          <SustainabilityCard label={t("gridNuclear")} value={shares30d.nuclear} color="#7c3aed" />
          <SustainabilityCard label={t("gridFossil")} value={shares30d.fossil} color="#78716c" />
          <CarbonCard label={t("gridCarbonIntensity")} value={co2_30d} />
        </div>

        <div className="mb-3 text-xs font-medium text-gray-500 uppercase tracking-wide">{t("gridLast180")}</div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <SustainabilityCard label={t("gridRenewable")} value={shares180d.renewable} color="#10b981" />
          <SustainabilityCard label={t("gridNuclear")} value={shares180d.nuclear} color="#7c3aed" />
          <SustainabilityCard label={t("gridFossil")} value={shares180d.fossil} color="#78716c" />
          <CarbonCard label={t("gridCarbonIntensity")} value={co2_180d} />
        </div>

        <p className="mt-4 text-xs text-gray-400">{t("gridCo2Footnote")}</p>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-gray-900">{t("gridGenerationTitle")}</h2>
          <div className="flex items-center gap-3">
            <SeriesFilterDropdown
              options={fuelTypes} selected={selectedFuels} onToggle={toggleFuel}
              onSelectAll={selectAllFuels} onClearAll={clearAllFuels} colors={FUEL_COLORS}
              isOpen={genFilterOpen} setIsOpen={setGenFilterOpen} label={t("gridFuelsLabel")}
              getLabel={(fuel) => translateFuel(fuel, lang)}
              selectAllLabel={t("gridSelectAll")} clearAllLabel={t("gridClearAll")}
            />
            <RangeSelector value={genRange} onChange={setGenRange} />
          </div>
        </div>
        <div className="w-full h-[380px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={genData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="t" tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} label={{ value: "MW", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }} />
              <Tooltip labelFormatter={(l) => fmtAxis(String(l))} />
              {fuelTypes.filter(f => selectedFuels.has(f)).map(fuel => (
                <Area
                  key={fuel} type="monotone" dataKey={fuel} stackId="1"
                  stroke={FUEL_COLORS[fuel] ?? "#9ca3af"}
                  fill={FUEL_COLORS[fuel] ?? "#9ca3af"}
                  fillOpacity={0.75}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-gray-900">{t("gridCrossborderTitle")}</h2>
          <div className="flex items-center gap-3">
            <SeriesFilterDropdown
              options={borders} selected={selectedBorders} onToggle={toggleBorder}
              onSelectAll={selectAllBorders} onClearAll={clearAllBorders}
              colors={Object.fromEntries(borders.map((b, i) => [b, BORDER_COLORS[i % BORDER_COLORS.length]]))}
              isOpen={flowFilterOpen} setIsOpen={setFlowFilterOpen} label={t("gridBordersLabel")}
              selectAllLabel={t("gridSelectAll")} clearAllLabel={t("gridClearAll")}
            />
            <RangeSelector value={flowRange} onChange={setFlowRange} />
          </div>
        </div>
        <div className="w-full h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={flowData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="t" tickFormatter={fmtAxis} tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} label={{ value: "MW", angle: -90, position: "insideLeft", style: { fontSize: 12, fill: "#6b7280" } }} />
              <Tooltip labelFormatter={(l) => fmtAxis(String(l))} />
              {borders.filter(b => selectedBorders.has(b)).map((border, i) => (
                <Area
                  key={border} type="monotone" dataKey={border} stackId={undefined}
                  stroke={BORDER_COLORS[i % BORDER_COLORS.length]}
                  fill={BORDER_COLORS[i % BORDER_COLORS.length]}
                  fillOpacity={0.2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-3 text-xs text-gray-400">{t("gridCrossborderNote")}</p>
      </section>
    </div>
  );
}
