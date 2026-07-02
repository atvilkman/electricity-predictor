"""
export_grid_snapshot.py — writes data/grid_snapshot.json from the ENTSO-E
Parquet files, for the Grid tab. Ships full 180-day window; frontend
filters client-side for the 7/30/180 day selector.
"""

import json
from pathlib import Path
import pandas as pd

LOAD_PATH = "data/entsoe_load.parquet"
GENERATION_PATH = "data/entsoe_generation.parquet"
CROSSBORDER_PATH = "data/entsoe_crossborder.parquet"
OUT_PATH = "data/grid_snapshot.json"


def ts_iso(x) -> str:
    return pd.Timestamp(x).isoformat()


def build_snapshot() -> dict:
    snap = {"generated_at": ts_iso(pd.Timestamp.now("UTC"))}

    if Path(LOAD_PATH).exists():
        load = pd.read_parquet(LOAD_PATH)
        snap["load"] = [
            {"t": ts_iso(r["timestamp"]), "mw": round(float(r["load_actual_mw"]), 1)}
            for _, r in load.iterrows()
        ]
    else:
        snap["load"] = []

    if Path(GENERATION_PATH).exists():
        gen = pd.read_parquet(GENERATION_PATH)
        snap["generation"] = [
            {"t": ts_iso(r["timestamp"]), "fuel": r["fuel_type"], "mw": round(float(r["mw"]), 1)}
            for _, r in gen.iterrows()
        ]
    else:
        snap["generation"] = []

    if Path(CROSSBORDER_PATH).exists():
        flows = pd.read_parquet(CROSSBORDER_PATH)
        snap["crossborder"] = [
            {"t": ts_iso(r["timestamp"]), "border": r["border"], "mw": round(float(r["mw"]), 1)}
            for _, r in flows.iterrows()
        ]
    else:
        snap["crossborder"] = []

    return snap


if __name__ == "__main__":
    snap = build_snapshot()
    Path("data").mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(snap, f)
    print(f"Written: {OUT_PATH}")
    print(f"  load rows: {len(snap['load'])}")
    print(f"  generation rows: {len(snap['generation'])}")
    print(f"  crossborder rows: {len(snap['crossborder'])}")
