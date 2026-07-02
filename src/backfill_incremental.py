"""
backfill_incremental.py — the daily-run companion to backfill_history.py.
Fetches only the last 48h of weather + Fingrid + prices and appends
(dedupe on timestamp). Runs in ~30 seconds vs the 3-5 minute full backfill.
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests

from backfill_history import (
    fetch_openmeteo_archive, fetch_fingrid_history,
    FINGRID_DATASETS,
)

FEATURES_PATH = "data/features_full_hourly.parquet"
PRICE_HISTORY_PATH = "data/price_history_hourly.parquet"
INCREMENTAL_HOURS = 48


def fetch_porssisahko_recent() -> pd.DataFrame:
    r = requests.get("https://api.porssisahko.net/v1/latest-prices.json", timeout=30)
    r.raise_for_status()
    rows = r.json()["prices"]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["startDate"], utc=True)
    df["price_eur_mwh"] = df["price"] * 10.0
    df["price_snt_kwh"] = df["price"] / 1.255
    return df[["timestamp", "price_eur_mwh", "price_snt_kwh"]].sort_values("timestamp")


def append_prices():
    existing = pd.read_parquet(PRICE_HISTORY_PATH)
    new = fetch_porssisahko_recent()
    combined = pd.concat([existing, new], ignore_index=True)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    combined.to_parquet(PRICE_HISTORY_PATH, index=False)
    added = len(combined) - len(existing)
    print(f"Prices: {len(existing)} -> {len(combined)} rows (+{added})")
    return combined


def append_features(prices: pd.DataFrame):
    existing = pd.read_parquet(FEATURES_PATH)
    now_utc = pd.Timestamp.now("UTC")
    window_start = now_utc - pd.Timedelta(hours=INCREMENTAL_HOURS)
    archive_end = now_utc - pd.Timedelta(days=5)
    start_date = window_start.strftime("%Y-%m-%d")
    end_date = archive_end.strftime("%Y-%m-%d")
    start_iso = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Incremental window: {window_start} -> {now_utc}")

    if archive_end > window_start:
        print("Fetching Open-Meteo Archive: Helsinki (incremental)...")
        hki = fetch_openmeteo_archive("helsinki", start_date, end_date)
        print(f"  Helsinki: {len(hki)} rows")
        print("Fetching Open-Meteo Archive: Vaasa (incremental)...")
        vaa = fetch_openmeteo_archive("vaasa", start_date, end_date)
        print(f"  Vaasa: {len(vaa)} rows")
    else:
        print("(archive lag exceeds window; skipping weather)")
        hki = pd.DataFrame(columns=["timestamp"])
        vaa = pd.DataFrame(columns=["timestamp"])

    print("Fetching Fingrid consumption (incremental)...")
    cons = fetch_fingrid_history(FINGRID_DATASETS["consumption_forecast_mw"], start_iso, end_iso)
    cons = cons.rename(columns={"value": "consumption_forecast_mw"})
    print(f"  Consumption: {len(cons)} rows")
    time.sleep(2.5)
    print("Fetching Fingrid wind (incremental)...")
    wind = fetch_fingrid_history(FINGRID_DATASETS["wind_forecast_mw"], start_iso, end_iso)
    wind = wind.rename(columns={"value": "wind_forecast_mw"})
    print(f"  Wind: {len(wind)} rows")
    time.sleep(2.5)
    print("Fetching Fingrid nuclear (incremental)...")
    nuclear = fetch_fingrid_history(FINGRID_DATASETS["nuclear_production_mw"], start_iso, end_iso)
    nuclear = nuclear.rename(columns={"value": "nuclear_production_mw"})
    print(f"  Nuclear: {len(nuclear)} rows")

    new_slice = prices[prices["timestamp"] >= window_start].copy()
    for df in [hki, vaa, cons, wind, nuclear]:
        if len(df) > 0:
            new_slice = new_slice.merge(df, on="timestamp", how="left")

    combined = pd.concat([existing, new_slice], ignore_index=True)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    added = len(combined) - len(existing)
    print(f"Features: {len(existing)} -> {len(combined)} rows (+{added})")
    combined.to_parquet(FEATURES_PATH, index=False)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)

    if not Path(FEATURES_PATH).exists():
        print(f"{FEATURES_PATH} not found — run backfill_history.py first.")
        raise SystemExit(1)

    prices = append_prices()
    append_features(prices)
    print("\nIncremental update complete.")
