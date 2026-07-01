"""
fetch.py — Phase 2: Data Ingestion

Currently implements: ENTSO-E historical price loading (BZN|FI).
Next additions (same file): porssisahko near-term, Fingrid grid data,
Open-Meteo weather.
"""

import re
import sys
import glob
import time
import pandas as pd

TZ_OFFSET = {"EET": "+02:00", "EEST": "+03:00"}
TAG_RE = re.compile(r"\((EEST|EET)\)")
DATETIME_RE = re.compile(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})")


def load_entsoe_csv(path: str) -> pd.DataFrame:
    """Load one ENTSO-E 'Export CSV year' day-ahead price file (BZN|FI)."""
    df = pd.read_csv(path)

    mtu = df["MTU (EET/EEST)"]
    start_field = mtu.str.split(" - ").str[0]
    start_clock = start_field.str.extract(DATETIME_RE, expand=False)

    tag_on_start = start_field.str.extract(TAG_RE, expand=False)
    tag_anywhere = mtu.str.extract(TAG_RE, expand=False)
    tag = tag_on_start.fillna(tag_anywhere)

    local_naive = pd.to_datetime(start_clock, format="%d/%m/%Y %H:%M:%S")

    no_tag_mask = tag.isna()
    ts_utc = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")

    if no_tag_mask.any():
        localized = local_naive[no_tag_mask].dt.tz_localize(
            "Europe/Helsinki", ambiguous="infer", nonexistent="shift_forward"
        )
        ts_utc.loc[no_tag_mask] = localized.dt.tz_convert("UTC")

    tagged_mask = ~no_tag_mask
    if tagged_mask.any():
        offsets = tag[tagged_mask].map(TZ_OFFSET)
        tagged_local = local_naive[tagged_mask].dt.tz_localize(None)
        tagged_utc = pd.to_datetime(
            tagged_local.astype(str) + offsets.values, utc=True
        )
        ts_utc.loc[tagged_mask] = tagged_utc

    price_eur_mwh = pd.to_numeric(df["Day-ahead Price (EUR/MWh)"], errors="coerce")

    return pd.DataFrame({"timestamp_utc": ts_utc, "price_eur_mwh": price_eur_mwh})


def build_hourly_price_history(csv_paths: list[str]) -> pd.DataFrame:
    """Combine yearly ENTSO-E CSVs into one clean hourly UTC price series."""
    frames = [load_entsoe_csv(p) for p in csv_paths]
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.drop_duplicates(subset="timestamp_utc").sort_values("timestamp_utc")

    raw = raw.set_index("timestamp_utc")
    hourly = raw["price_eur_mwh"].resample("1h").mean().to_frame()
    hourly["price_snt_kwh"] = hourly["price_eur_mwh"] / 10.0
    hourly = hourly.reset_index().rename(columns={"timestamp_utc": "timestamp"})

    return hourly[["timestamp", "price_eur_mwh", "price_snt_kwh"]]


def sanity_check(hourly: pd.DataFrame) -> None:
    n = len(hourly)
    start, end = hourly["timestamp"].min(), hourly["timestamp"].max()
    expected = int((end - start).total_seconds() // 3600) + 1
    missing = expected - n

    print(f"Rows (hours):          {n}")
    print(f"Date range (UTC):      {start} -> {end}")
    print(f"Missing hours:         {missing}")
    print(f"NaN price rows:        {hourly['price_snt_kwh'].isna().sum()}")
    print(f"Price range (snt/kWh): {hourly['price_snt_kwh'].min():.2f} to {hourly['price_snt_kwh'].max():.2f}")
    print(f"Mean price (snt/kWh):  {hourly['price_snt_kwh'].mean():.2f}")


if __name__ == "__main__":
    paths = sys.argv[1:] if len(sys.argv) > 1 else glob.glob("data/*.csv")
    if not paths:
        print("No CSV files found. Pass paths or place ENTSO-E CSVs in data/.")
        sys.exit(1)

    print(f"Loading {len(paths)} file(s): {paths}\n")
    hourly = build_hourly_price_history(paths)
    sanity_check(hourly)

    out_path = "data/price_history_hourly.parquet"
    hourly.to_parquet(out_path, index=False)
    print(f"\nWritten: {out_path}")


import os
import requests

FINGRID_BASE = "https://data.fingrid.fi/api/datasets/{id}/data"

FINGRID_DATASETS = {
    "consumption_forecast_mw": 166,  # 72h ahead, 15-min
    "wind_forecast_mw": 245,          # 36h ahead, 15-min
}


def fetch_fingrid_dataset(dataset_id: int, start_iso: str, end_iso: str) -> pd.DataFrame:
    """Fetch one Fingrid dataset over [start_iso, end_iso) as hourly-mean values."""
    api_key = os.environ["FINGRID_API_KEY"]
    url = FINGRID_BASE.format(id=dataset_id)
    headers = {"x-api-key": api_key}
    params = {
        "startTime": start_iso,
        "endTime": end_iso,
        "format": "json",
        "pageSize": 20000,
        "oneRowPerTimePeriod": "true",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    rows = payload.get("data", payload)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    df["timestamp"] = pd.to_datetime(df["startTime"], utc=True)
    known_cols = {"startTime", "endTime", "datasetId", "timestamp"}
    value_col = [c for c in df.columns if c not in known_cols][0]
    df["value"] = pd.to_numeric(df[value_col], errors="coerce")
    df = df[["timestamp", "value"]].set_index("timestamp")
    return df.resample("1h").mean().reset_index()


def fetch_fingrid_forecasts(hours_ahead: int = 72) -> pd.DataFrame:
    """Pull consumption + wind forecasts and merge into one hourly frame."""
    now = pd.Timestamp.utcnow()
    start_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = (now + pd.Timedelta(hours=hours_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

    consumption = fetch_fingrid_dataset(
        FINGRID_DATASETS["consumption_forecast_mw"], start_iso, end_iso
    ).rename(columns={"value": "consumption_forecast_mw"})

    time.sleep(2)

    wind = fetch_fingrid_dataset(
        FINGRID_DATASETS["wind_forecast_mw"], start_iso, end_iso
    ).rename(columns={"value": "wind_forecast_mw"})

    merged = pd.merge(consumption, wind, on="timestamp", how="outer").sort_values("timestamp")
    return merged


OPEN_METEO_LOCATIONS = {
    "helsinki": (60.1699, 24.9384),
    "vaasa": (63.0960, 21.6158),
}


def fetch_open_meteo(location: str = "helsinki", days_ahead: int = 10) -> pd.DataFrame:
    """Fetch hourly weather forecast (temp + wind) from Open-Meteo."""
    lat, lon = OPEN_METEO_LOCATIONS[location]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_speed_10m",
        "forecast_days": days_ahead,
        "timezone": "UTC",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()["hourly"]

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(payload["time"], utc=True),
        f"temp_c_{location}": payload["temperature_2m"],
        f"wind_ms_{location}": payload["wind_speed_10m"],
    })
    return df


def fetch_all_weather(days_ahead: int = 10) -> pd.DataFrame:
    """Merge Helsinki + Vaasa weather forecasts into one hourly frame."""
    helsinki = fetch_open_meteo("helsinki", days_ahead)
    vaasa = fetch_open_meteo("vaasa", days_ahead)
    return pd.merge(helsinki, vaasa, on="timestamp", how="outer").sort_values("timestamp")


def fetch_porssisahko() -> pd.DataFrame:
    """Fetch near-term known spot prices (~36h) from porssisahko.net."""
    url = "https://api.porssisahko.net/v2/latest-prices.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()["prices"]

    df = pd.DataFrame(payload)
    df["timestamp"] = pd.to_datetime(df["startDate"], utc=True)
    df["price_snt_kwh"] = pd.to_numeric(df["price"], errors="coerce") / 10.0

    df = df[["timestamp", "price_snt_kwh"]].sort_values("timestamp")
    df = df.set_index("timestamp").resample("1h").mean().reset_index()
    return df
