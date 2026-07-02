"""
fetch_entsoe_grid.py — pulls Finnish grid data from ENTSO-E Transparency
Platform: actual load, generation by fuel type, and cross-border physical
flows (SE1, SE3, EE). Powers the Grid tab (informational only, not used
as model features).
"""

import os
import pandas as pd
from entsoe import EntsoePandasClient

LOAD_PATH = "data/entsoe_load.parquet"
GENERATION_PATH = "data/entsoe_generation.parquet"
CROSSBORDER_PATH = "data/entsoe_crossborder.parquet"

CROSSBORDER_ZONES = ["SE_1", "SE_3", "EE"]
ROLLING_DAYS = 180


def get_client() -> EntsoePandasClient:
    token = os.environ["ENTSOE_API_TOKEN"]
    return EntsoePandasClient(api_key=token)


def fetch_load(client, start, end) -> pd.DataFrame:
    df = client.query_load("FI", start=start, end=end)
    df = df.reset_index()
    df.columns = ["timestamp", "load_actual_mw"]
    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    return df


def fetch_generation(client, start, end) -> pd.DataFrame:
    df = client.query_generation("FI", start=start, end=end, psr_type=None)
    # entsoe-py returns MultiIndex columns: (fuel_type, 'Actual Aggregated').
    # Keep only the 'Actual Aggregated' sub-column per fuel type and flatten.
    if isinstance(df.columns, pd.MultiIndex):
        actual = [col for col in df.columns if col[1] == "Actual Aggregated"]
        df = df[actual]
        df.columns = [col[0] for col in actual]
    df.index.name = "timestamp"
    df = df.reset_index()
    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    long_df = df.melt(id_vars="timestamp", var_name="fuel_type", value_name="mw")
    long_df = long_df.dropna(subset=["mw"])
    return long_df


def fetch_crossborder(client, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """
    Fetch day-by-day rather than one large range. Finland's ENTSO-E
    cross-border feed mixes 15-min and 60-min resolution segments over time,
    which trips entsoe-py's internal merge when spanning many days at once.
    Single-day chunks avoid the resolution boundary within one request.
    """
    rows = []
    day = start.normalize()
    end_day = end.normalize()
    while day <= end_day:
        day_end = min(day + pd.Timedelta(days=1), end)
        for zone in CROSSBORDER_ZONES:
            try:
                imp = client.query_crossborder_flows(zone, "FI", start=day, end=day_end)
                imp_df = imp.reset_index()
                imp_df.columns = ["timestamp", "mw"]
                imp_df["border"] = f"{zone.replace('_', '')}->FI"
                rows.append(imp_df)
            except Exception as e:
                print(f"  Import flow {zone}->FI failed on {day.date()}: {e}")
            try:
                exp = client.query_crossborder_flows("FI", zone, start=day, end=day_end)
                exp_df = exp.reset_index()
                exp_df.columns = ["timestamp", "mw"]
                exp_df["border"] = f"FI->{zone.replace('_', '')}"
                rows.append(exp_df)
            except Exception as e:
                print(f"  Export flow FI->{zone} failed on {day.date()}: {e}")
        day += pd.Timedelta(days=1)

    if not rows:
        return pd.DataFrame(columns=["timestamp", "border", "mw"])
    combined = pd.concat(rows, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    combined = (
        combined.set_index("timestamp")
        .groupby("border")["mw"]
        .resample("1h").mean()
        .reset_index()
    )
    return combined


def _merge_and_trim(existing_path, new_df, dedup_cols):
    if os.path.exists(existing_path):
        existing = pd.read_parquet(existing_path)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
    combined = combined.sort_values("timestamp")
    cutoff = pd.Timestamp.now("UTC") - pd.Timedelta(days=ROLLING_DAYS)
    combined = combined[combined["timestamp"] >= cutoff].reset_index(drop=True)
    return combined


def run(days_back: int):
    client = get_client()
    end = pd.Timestamp.now(tz="Europe/Helsinki")
    start = end - pd.Timedelta(days=days_back)
    print(f"Fetching ENTSO-E grid data: {start} -> {end}")

    print("Fetching load...")
    load = fetch_load(client, start, end)
    print(f"  {len(load)} rows")
    load_combined = _merge_and_trim(LOAD_PATH, load, ["timestamp"])
    load_combined.to_parquet(LOAD_PATH, index=False)
    print(f"  Total after merge: {len(load_combined)} rows")

    print("Fetching generation by fuel type...")
    gen = fetch_generation(client, start, end)
    print(f"  {len(gen)} rows")
    gen_combined = _merge_and_trim(GENERATION_PATH, gen, ["timestamp", "fuel_type"])
    gen_combined.to_parquet(GENERATION_PATH, index=False)
    print(f"  Total after merge: {len(gen_combined)} rows")

    print("Fetching cross-border flows...")
    # Day-by-day chunking is slow (many requests), so cap this series to the
    # most recent 30 days regardless of the overall backfill range. Load and
    # generation stay at the full range since bulk fetch works for those.
    crossborder_start = max(start, end - pd.Timedelta(days=30))
    flows = fetch_crossborder(client, crossborder_start, end)
    print(f"  {len(flows)} rows")
    flows_combined = _merge_and_trim(CROSSBORDER_PATH, flows, ["timestamp", "border"])
    flows_combined.to_parquet(CROSSBORDER_PATH, index=False)
    print(f"  Total after merge: {len(flows_combined)} rows")


def bootstrap():
    run(days_back=ROLLING_DAYS)


def incremental():
    run(days_back=2)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv(override=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    if mode == "bootstrap":
        bootstrap()
    else:
        incremental()
    print("\nDone.")
