export type LoadRow = { t: string; mw: number };
export type GenerationRow = { t: string; fuel: string; mw: number };
export type CrossborderRow = { t: string; border: string; mw: number };
export type GridSnapshot = {
  generated_at: string;
  load: LoadRow[];
  generation: GenerationRow[];
  crossborder: CrossborderRow[];
};

export async function loadGridSnapshot(): Promise<GridSnapshot> {
  const base = process.env.NODE_ENV === "production" ? "/electricity-predictor" : "";
  const res = await fetch(`${base}/data/grid_snapshot.json`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load grid snapshot: ${res.status}`);
  return res.json();
}

export function filterByDays<T extends { t: string }>(rows: T[], days: number): T[] {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return rows.filter(r => new Date(r.t).getTime() >= cutoff);
}
