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

    # Forecast vs Actual: all predictions that have a matching actual
    joined = pd.read_sql("""
        SELECT p.target_timestamp AS t, p.made_at, p.horizon_hours,
               p.predicted_price_snt_kwh AS predicted,
               a.actual_price_snt_kwh AS actual
        FROM predictions p
        JOIN actuals a ON p.target_timestamp = a.target_timestamp
        ORDER BY p.target_timestamp, p.made_at
    """, conn)
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

    # Forecast vs Actual records
    vs_actual = []
    for _, r in joined.iterrows():
        vs_actual.append({
            "t": ts_iso(r["t"]),
            "made_at": ts_iso(r["made_at"]),
            "horizon_h": int(r["horizon_hours"]),
            "predicted": round(float(r["predicted"]), 3),
            "actual": round(float(r["actual"]), 3),
        })

    # Live accuracy per horizon (from real frozen forecasts)
    live_accuracy = []
    if not joined.empty:
        for h in [24, 48, 72, 96, 120]:
            hdf = joined[joined["horizon_hours"] == h]
            if len(hdf) > 0:
                mae = float(abs(hdf["predicted"] - hdf["actual"]).mean())
                live_accuracy.append({
                    "horizon_h": h,
                    "label": f"N+{h // 24}",
                    "mae": round(mae, 3),
                    "n": len(hdf),
                })

    # Validation accuracy (from training, model vs naive-week baseline)
    validation_accuracy = []
    if Path(VALIDATION_RESULTS_PATH).exists():
        vdf = pd.read_parquet(VALIDATION_RESULTS_PATH)
        for _, r in vdf.iterrows():
            validation_accuracy.append({
                "horizon_h": int(r["horizon_hours"]),
                "label": str(r["horizon_label"]),
                "model_mae": round(float(r["model_mae_snt_kwh"]), 3),
                "naive_mae": round(float(r["naive_week_mae_snt_kwh"]), 3),
                "beats_naive": bool(r["beats_naive"]),
                "n_val": int(r["n_val"]),
            })

    return {
        "generated_at": ts_iso(now_utc),
        "known": recent_records,
        "forecast": forecast_records,
        "mae_by_horizon": mae_by_horizon,
        "thresholds": {"cheap": 2.0, "expensive": 15.0},
        "vs_actual": vs_actual,
        "live_accuracy": live_accuracy,
        "validation_accuracy": validation_accuracy,
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
