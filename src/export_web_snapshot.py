"""
export_web_snapshot.py — writes a JSON snapshot of everything the web
dashboard needs to render, in one file at data/web_snapshot.json.

Runs after fetch/train/generate_forecast, before commit. The React app
fetches this file directly at page load.
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = "data/electricity.db"
PRICE_HISTORY_PATH = "data/price_history_hourly.parquet"
VALIDATION_RESULTS_PATH = "data/model_validation_results.parquet"
OUT_PATH = "data/web_snapshot.json"


def ts_iso(x) -> str:
    return pd.Timestamp(x).isoformat()


def build_snapshot() -> dict:
    now_utc = pd.Timestamp.now("UTC")

    # Recent known prices — last 48 hours is enough for the "known" section
    history = pd.read_parquet(PRICE_HISTORY_PATH)
    recent = history[history["timestamp"] >= now_utc - pd.Timedelta(hours=36)].copy()
    recent_records = [
        {"t": ts_iso(r["timestamp"]), "p": round(float(r["price_snt_kwh"]), 3)}
        for _, r in recent.iterrows()
    ]

    # Latest forecast (all horizons from the most recent made_at)
    conn = sqlite3.connect(DB_PATH)
    preds = pd.read_sql("SELECT * FROM predictions", conn)
    conn.close()
    forecast_records = []
    if not preds.empty:
        preds["made_at"] = pd.to_datetime(preds["made_at"], utc=True)
        latest = preds[preds["made_at"] == preds["made_at"].max()]
        for _, r in latest.iterrows():
            forecast_records.append({
                "t": ts_iso(r["target_timestamp"]),
                "p": round(float(r["predicted_price_snt_kwh"]), 3),
                "horizon_h": int(r["horizon_hours"]),
                "horizon_label": f"N+{int(r['horizon_hours']) // 24}",
            })

    # Per-horizon MAE (for uncertainty bands)
    mae_by_horizon = {}
    if Path(VALIDATION_RESULTS_PATH).exists():
        vdf = pd.read_parquet(VALIDATION_RESULTS_PATH)
        mae_by_horizon = {int(h): round(float(m), 3) for h, m
                           in zip(vdf["horizon_hours"], vdf["model_mae_snt_kwh"])}

    return {
        "generated_at": ts_iso(now_utc),
        "known": recent_records,
        "forecast": forecast_records,
        "mae_by_horizon": mae_by_horizon,
        "thresholds": {"cheap": 2.0, "expensive": 15.0},
    }


if __name__ == "__main__":
    snap = build_snapshot()
    Path("data").mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(snap, f, indent=2)
    print(f"Written: {OUT_PATH}")
    print(f"  known rows:     {len(snap['known'])}")
    print(f"  forecast rows:  {len(snap['forecast'])}")
    print(f"  mae horizons:   {list(snap['mae_by_horizon'].keys())}")
