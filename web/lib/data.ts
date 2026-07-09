export type PriceRow = { t: string; p: number };
export type ForecastRow = {
  t: string; p: number; horizon_h: number; horizon_label: string;
};
export type VsActualRecord = {
  t: string; made_at: string; horizon_h: number; predicted: number; actual: number;
};
export type LiveAccRow = { horizon_h: number; label: string; mae: number; n: number };
export type ValAccRow = {
  horizon_h: number; label: string;
  model_mae: number; naive_mae: number; beats_naive: boolean; n_val: number;
};
export type Snapshot = {
  generated_at: string;
  known: PriceRow[];
  forecast: ForecastRow[];
  mae_by_horizon: Record<string, number>;
  thresholds: { cheap: number; expensive: number };
  vs_actual: VsActualRecord[];
  live_accuracy: LiveAccRow[];
  validation_accuracy: ValAccRow[];
};

export async function loadSnapshot(): Promise<Snapshot> {
  const base = process.env.NODE_ENV === "production"
    ? "/electricity-predictor" : "";
  const res = await fetch(`${base}/data/web_snapshot.json`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load snapshot: ${res.status}`);
  return res.json();
}
