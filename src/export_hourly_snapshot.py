"""
export_hourly_snapshot.py — writes data/hourly_snapshot.json from the
latest frozen hourly_predictions, for the new Hourly tab.
"""

import json
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = "data/electricity.db"
OUT_PATH = "data/hourly_snapshot.json"


def ts_iso(x) -> str:
    return pd.Timestamp(x).isoformat()


def build_snapshot() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        preds = pd.read_sql("SELECT * FROM hourly_predictions", conn)
    except Exception:
        preds = pd.DataFrame(columns=["target_timestamp", "made_at", "horizon_hours", "predicted_price_snt_kwh"])
    conn.close()

    records = []
    if not preds.empty:
        preds["made_at"] = pd.to_datetime(preds["made_at"], utc=True)
        latest = preds[preds["made_at"] == preds["made_at"].max()]
        latest = latest.sort_values("horizon_hours")
        for _, r in latest.iterrows():
            records.append({
                "t": ts_iso(r["target_timestamp"]),
                "p": round(float(r["predicted_price_snt_kwh"]), 3),
                "horizon_h": int(r["horizon_hours"]),
            })

    return {"generated_at": ts_iso(pd.Timestamp.now("UTC")), "hourly": records}


if __name__ == "__main__":
    snap = build_snapshot()
    Path("data").mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(snap, f)
    print(f"Written: {OUT_PATH}")
    print(f"  hourly points: {len(snap['hourly'])}")
