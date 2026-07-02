"use client";
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Scatter, LabelList,
} from "recharts";
import type { Snapshot } from "@/lib/data";
import { useLanguage } from "@/lib/i18n";

type Point = {
  t: number;
  known?: number;
  knownArea?: number;
  forecast?: number;
  upper?: number;
  lower?: number;
  current?: number;
  isForecastBridge?: boolean;
};

function fmtAxis(v: number): string {
  const d = new Date(v);
  return d.toLocaleString("en-GB", {
    timeZone: "Europe/Helsinki",
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}
function fmtTooltip(v: number): string {
  const d = new Date(v);
  return d.toLocaleString("en-GB", {
    timeZone: "Europe/Helsinki",
    weekday: "short", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit",
  });
}

function buildDailyTicks(start: number, end: number): number[] {
  const ticks: number[] = [];
  const d = new Date(start);
  d.setUTCMinutes(0, 0, 0);
  d.setUTCHours(12);
  while (d.getTime() < start) d.setUTCDate(d.getUTCDate() + 1);
  while (d.getTime() <= end) {
    ticks.push(d.getTime());
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return ticks;
}

type TooltipEntry = {
  payload?: Point;
  dataKey?: string | number | ((obj: unknown) => unknown);
  value?: number | string | readonly (string | number)[] | null;
};

// Stable top-level component — never remounts between renders.
// Filters payload by dataKey so upper/lower/knownArea/current never win.
function ForecastTooltip(props: {
  active?: boolean;
  payload?: readonly TooltipEntry[];
}) {
  const { t } = useLanguage();
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;

  const priceEntry = payload.find(
    e =>
      (e.dataKey === "known" || e.dataKey === "forecast") &&
      typeof e.value === "number" &&
      e.payload
  );

  const row =
    priceEntry?.payload ??
    payload.map(e => e.payload).find(p => p?.known !== undefined || p?.forecast !== undefined);

  if (!row) return null;

  const time = fmtTooltip(row.t);
  const rows: { label: string; value: string; color: string }[] = [];

  if (row.known !== undefined) {
    rows.push({
      label: t("tooltipKnown"),
      value: `${row.known.toFixed(2)} snt/kWh`,
      color: "#1f77b4",
    });
  }

  // Bridge point has forecast set to the known value — skip showing "Forecast" for it
  if (row.forecast !== undefined && !row.isForecastBridge) {
    rows.push({
      label: t("tooltipForecast"),
      value: `${row.forecast.toFixed(2)} snt/kWh`,
      color: "#1f77b4",
    });
    if (row.upper !== undefined && row.lower !== undefined) {
      rows.push({
        label: t("tooltipRange"),
        value: `${row.lower.toFixed(2)} – ${row.upper.toFixed(2)} snt/kWh`,
        color: "#94a3b8",
      });
    }
  }

  if (rows.length === 0) return null;

  return (
    <div style={{
      background: "white",
      border: "1px solid #e5e7eb",
      borderRadius: 10,
      padding: "10px 14px",
      fontSize: 13,
      boxShadow: "0 4px 12px rgba(0,0,0,0.06)",
    }}>
      <div style={{ color: "#6b7280", fontSize: 12, marginBottom: 6 }}>{time}</div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 12, color: r.color }}>
          <span>{r.label}</span>
          <span style={{ fontWeight: 600 }}>{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function ForecastChart({ snap }: { snap: Snapshot }) {
  const { t } = useLanguage();
  const now = Date.now();

  const currentKnown = [...snap.known]
    .reverse()
    .find(r => new Date(r.t).getTime() <= now);

  const currentT = currentKnown ? new Date(currentKnown.t).getTime() : null;

  const knownPts: Point[] = snap.known.map(r => {
    const ts = new Date(r.t).getTime();
    return {
      t: ts,
      known: r.p,
      knownArea: r.p,
      forecast: undefined,
      upper: undefined,
      lower: undefined,
      // current only set on the one matching timestamp — Scatter renders there
      current: currentT === ts ? r.p : undefined,
    };
  });

  const fcPts: Point[] = snap.forecast.map(r => {
    const mae = snap.mae_by_horizon[String(r.horizon_h)] ?? 0;
    const horizonScale = Math.min(1, 0.5 + r.horizon_h / 240);
    const halfBand = mae * horizonScale;
    const upper = r.p + halfBand;
    const lower = Math.max(r.p * 0.3, r.p - halfBand * 0.6);
    return {
      t: new Date(r.t).getTime(),
      forecast: r.p,
      upper,
      lower,
      known: undefined,
      knownArea: undefined,
    };
  });

  // Bridge: stamp the last known point with a forecast value so the dashed line
  // starts there, eliminating the visual gap to the first real forecast dot.
  const lastKnownPt = knownPts.at(-1);
  if (lastKnownPt && fcPts.length > 0 && fcPts[0].t > lastKnownPt.t) {
    lastKnownPt.forecast = lastKnownPt.known;
    lastKnownPt.isForecastBridge = true;
  }

  const data = [...knownPts, ...fcPts].sort((a, b) => a.t - b.t);
  if (data.length === 0) return null;

  const domainStart = data[0].t;
  const domainEnd = data[data.length - 1].t;
  const ticks = buildDailyTicks(domainStart, domainEnd);

  // Suppress the dot at the bridge point; normal dots for real forecast points.
  const forecastDot = (props: { cx?: number; cy?: number; payload?: Point }) => {
    if (props.payload?.isForecastBridge || props.cx == null || props.cy == null) {
      return <g />;
    }
    return (
      <circle cx={props.cx} cy={props.cy} r={6} fill="#1f77b4" stroke="#ffffff" strokeWidth={2} />
    );
  };

  return (
    <>
    <div className="w-full h-[460px]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 40, right: 40, left: 20, bottom: 20 }}>
          <defs>
            <linearGradient id="knownGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1f77b4" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#1f77b4" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="t" type="number" scale="time"
            domain={[domainStart, domainEnd]}
            ticks={ticks}
            tickFormatter={fmtAxis}
            tick={{ fontSize: 12, fill: "#4b5563" }}
            stroke="#9ca3af"
          />
          <YAxis
            tick={{ fontSize: 12, fill: "#4b5563" }}
            stroke="#9ca3af"
            label={{ value: "snt/kWh", angle: -90, position: "insideLeft", style: { fill: "#4b5563", fontSize: 13 } }}
          />
          <Tooltip content={ForecastTooltip} />
          {/* tooltipType="none" keeps these visual-only series out of the payload */}
          <Area dataKey="upper" stroke="none" fill="#3b82f6" fillOpacity={0.15} isAnimationActive={false} {...{ tooltipType: "none" }} />
          <Area dataKey="lower" stroke="none" fill="#ffffff" fillOpacity={1} isAnimationActive={false} legendType="none" {...{ tooltipType: "none" }} />
          <ReferenceLine
            y={snap.thresholds.cheap} stroke="#10b981" strokeDasharray="4 4"
            label={{ value: t("thresholdCheap"), position: "insideBottomLeft", fill: "#10b981", fontSize: 11, offset: 15 }}
          />
          <ReferenceLine
            y={snap.thresholds.expensive} stroke="#ef4444" strokeDasharray="4 4"
            label={{ value: t("thresholdExpensive"), position: "insideTopLeft", fill: "#ef4444", fontSize: 11 }}
          />
          <ReferenceLine
            x={now} stroke="#374151" strokeDasharray="2 2" strokeWidth={1.5}
            label={{ value: t("refNow"), position: "top", fill: "#374151", fontSize: 12, fontWeight: 600 }}
          />
          <Area dataKey="knownArea" stroke="none" fill="url(#knownGradient)" isAnimationActive={false} legendType="none" {...{ tooltipType: "none" }} />
          <Line dataKey="known" stroke="#1f77b4" strokeWidth={2.5} dot={false} isAnimationActive={false} connectNulls={false} />
          {/* Uses chart-level data via dataKey="current" — no separate data prop,
              so it doesn't create a second coordinate universe that breaks tooltip payload */}
          {currentKnown && (
            <Scatter
              dataKey="current"
              fill="#1f77b4"
              {...{ tooltipType: "none" }}
              shape={(props: { cx?: number; cy?: number; payload?: Point }) => {
                if (!props.payload?.current || props.cx == null || props.cy == null) return <g />;
                const { cx, cy } = props;
                return (
                  <g>
                    <circle cx={cx} cy={cy} r={7} fill="#ffffff" stroke="#1f77b4" strokeWidth={2.5} />
                    <circle cx={cx} cy={cy} r={3} fill="#1f77b4" />
                    <text x={cx + 8} y={cy - 18} fill="#1f77b4" fontSize={12} fontWeight={600}>
                      {props.payload.current.toFixed(2)} snt/kWh
                    </text>
                  </g>
                );
              }}
            />
          )}
          <Line
            dataKey="forecast"
            stroke="#1f77b4"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={forecastDot}
            isAnimationActive={false}
            connectNulls={false}
          >
            <LabelList
              dataKey="forecast"
              position="top"
              offset={12}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              content={(props: any) => {
                const x = props.x as string | number | undefined;
                const y = props.y as string | number | undefined;
                const value = props.value;
                const index = props.index as number | undefined;
                if (typeof value !== "number" || index === undefined) return null;
                if (data[index]?.isForecastBridge) return null;
                const numY = typeof y === "number" ? y : parseFloat(String(y ?? "0"));
                return (
                  <text
                    x={x}
                    y={numY - 12}
                    fill="#1f77b4"
                    fontSize={12}
                    fontWeight={600}
                    textAnchor="middle"
                  >
                    {value.toFixed(1)}
                  </text>
                );
              }}
            />
          </Line>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
    <p className="mt-3 text-xs text-gray-400">{t("bandNote")}</p>
    </>
  );
}
