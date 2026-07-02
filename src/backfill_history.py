"""
backfill_history.py — pulls historical weather (Open-Meteo Archive API) and
Fingrid consumption+wind history, merges them with the price history on the
hourly timestamp, and writes data/features_full_hourly.parquet.
"""

import os
import time
import pandas as pd
import requests

OPEN_METEO_LOCATIONS = {
    "helsinki": (60.1699, 24.9384),
    "vaasa": (63.0960, 21.6158),
}
FINGRID_BASE = "https://data.fingrid.fi/api/datasets/{id}/data"
FINGRID_DATASETS = {
    "consumption_forecast_mw": 166,
    "wind_forecast_mw": 245,
    "nuclear_production_mw": 188,
}


def fetch_openmeteo_archive(location: str, start_date: str, end_date: str) -> pd.DataFrame:
    lat, lon = OPEN_METEO_LOCATIONS[location]
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "hourly": "temperature_2m,wind_speed_10m",
        "timezone": "UTC",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    return pd.DataFrame({
        "timestamp": pd.to_datetime(h["time"], utc=True),
        f"temp_c_{location}": h["temperature_2m"],
        f"wind_ms_{location}": h["wind_speed_10m"],
    })


def fetch_fingrid_history(dataset_id: int, start_iso: str, end_iso: str) -> pd.DataFrame:
    # Fetch in 6-month chunks so each request stays well under the API's 10000-row
    # silent cap (6 months ≈ 4380 rows, comfortably below the limit).
    api_key = os.environ["FINGRID_API_KEY"]
    url = FINGRID_BASE.format(id=dataset_id)
    headers = {"x-api-key": api_key}

    start_ts = pd.Timestamp(start_iso, tz="UTC")
    end_ts = pd.Timestamp(end_iso, tz="UTC")
    all_rows: list = []
    current = start_ts

    while current < end_ts:
        chunk_end = min(current + pd.DateOffset(months=6), end_ts)
        params = {
            "startTime": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endTime": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "format": "json", "pageSize": 20000, "page": 1,
            "oneRowPerTimePeriod": "true",
        }
        r = requests.get(url, headers=headers, params=params, timeout=60)
        r.raise_for_status()
        rows = r.json().get("data", [])
        all_rows.extend(rows)
        current = chunk_end
        if current < end_ts:
            time.sleep(2.2)

    if not all_rows:
        return pd.DataFrame(columns=["timestamp", "value"])
    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["startTime"], utc=True)
    known = {"startTime", "endTime", "datasetId", "timestamp"}
    value_col = [c for c in df.columns if c not in known][0]
    df["value"] = pd.to_numeric(df[value_col], errors="coerce")
    return df[["timestamp", "value"]].set_index("timestamp").resample("1h").mean().reset_index()


def build_full_features():
    from dotenv import load_dotenv
    load_dotenv(override=True)

    price_df = pd.read_parquet("data/price_history_hourly.parquet")
    print(f"Price history: {len(price_df)} rows")

    start_dt = price_df["timestamp"].min()
    end_dt = price_df["timestamp"].max()
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")
    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Archive API only covers past data; cap at 5 days before today to be safe.
    archive_end = min(end_dt, pd.Timestamp.now("UTC") - pd.Timedelta(days=5))
    archive_end_date = archive_end.strftime("%Y-%m-%d")

    print("Fetching Open-Meteo Archive: Helsinki...")
    hki = fetch_openmeteo_archive("helsinki", start_date, archive_end_date)
    print(f"  Helsinki: {len(hki)} rows")
    print("Fetching Open-Meteo Archive: Vaasa...")
    vaa = fetch_openmeteo_archive("vaasa", start_date, archive_end_date)
    print(f"  Vaasa: {len(vaa)} rows")

    print("Fetching Fingrid consumption forecast history...")
    cons = fetch_fingrid_history(FINGRID_DATASETS["consumption_forecast_mw"], start_iso, end_iso)
    cons = cons.rename(columns={"value": "consumption_forecast_mw"})
    print(f"  Consumption: {len(cons)} rows")
    time.sleep(2.5)
    print("Fetching Fingrid wind forecast history...")
    wind = fetch_fingrid_history(FINGRID_DATASETS["wind_forecast_mw"], start_iso, end_iso)
    wind = wind.rename(columns={"value": "wind_forecast_mw"})
    print(f"  Wind: {len(wind)} rows")
    print("Fetching Fingrid nuclear production history...")
    time.sleep(2.5)
    nuclear = fetch_fingrid_history(FINGRID_DATASETS["nuclear_production_mw"], start_iso, end_iso)
    nuclear = nuclear.rename(columns={"value": "nuclear_production_mw"})
    print(f"  Nuclear: {len(nuclear)} rows")

    merged = price_df.copy()
    for df in [hki, vaa, cons, wind, nuclear]:
        if len(df) > 0:
            merged = merged.merge(df, on="timestamp", how="left")

    print(f"\nMerged: {len(merged)} rows, columns: {list(merged.columns)}")
    nans = merged.isna().sum()
    print(f"NaN counts (per column):\n{nans[nans > 0]}")

    out = "data/features_full_hourly.parquet"
    merged.to_parquet(out, index=False)
    print(f"\nWritten: {out}")


if __name__ == "__main__":
    build_full_features()
