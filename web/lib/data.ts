export type PriceRow = { t: string; p: number };
export type ForecastRow = {
  t: string; p: number; horizon_h: number; horizon_label: string;
};
export type Snapshot = {
  generated_at: string;
  known: PriceRow[];
  forecast: ForecastRow[];
  mae_by_horizon: Record<string, number>;
  thresholds: { cheap: number; expensive: number };
};

export async function loadSnapshot(): Promise<Snapshot> {
  const base = process.env.NODE_ENV === "production"
    ? "/electricity-predictor" : "";
  const res = await fetch(`${base}/data/web_snapshot.json`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load snapshot: ${res.status}`);
  return res.json();
}
