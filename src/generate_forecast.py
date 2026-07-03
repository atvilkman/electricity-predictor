"""
generate_forecast.py — trains on full history, then builds a CORRECT
per-horizon feature row for each forecast point (calendar features match
the actual target hour, not "now"), using live Open-Meteo forecast data
instead of the stale 5-day-lagged archive.
"""

import sqlite3
import time
import numpy as np
import pandas as pd
import requests
import lightgbm as lgb

from features import build_features, features_available_at_horizon, add_calendar_features

HORIZONS_HOURS = [24, 48, 72, 96, 120]
FEATURES_PATH = "data/features_full_hourly.parquet"
DB_PATH = "data/electricity.db"

OPEN_METEO_LOCATIONS = {
    "helsinki": (60.1699, 24.9384),
    "vaasa": (63.0960, 21.6158),
}


def train_full_models(feats: pd.DataFrame) -> dict:
    models = {}
    for h in HORIZONS_HOURS:
        feature_cols = [c for c in features_available_at_horizon(h) if c in feats.columns]
        df = feats.copy()
        df["target"] = df["price_snt_kwh"].shift(-h)
        # Only drop rows missing the target. LightGBM handles NaN in features natively.
        usable = df.dropna(subset=["target"])
        model = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=31, random_state=42, verbosity=-1,
        )
        model.fit(usable[feature_cols], usable["target"])
        models[h] = (model, feature_cols)
        print(f"  N+{h//24}: trained on {len(usable)} rows, {len(feature_cols)} features")
    return models


def fetch_live_weather_forecast() -> dict:
    """Fetch real-time Open-Meteo forecast (not archive) for both locations,
    keyed by UTC hour timestamp. No lag — this is the live fix."""
    forecast_by_time: dict = {}
    for loc, (lat, lon) in OPEN_METEO_LOCATIONS.items():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m",
            "forecast_days": 7, "timezone": "UTC",
        }
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=60)
                r.raise_for_status()
                h = r.json()["hourly"]
                times = pd.to_datetime(h["time"], utc=True)
                for t_, temp, wind in zip(times, h["temperature_2m"], h["wind_speed_10m"]):
                    forecast_by_time.setdefault(t_, {})
                    forecast_by_time[t_][f"temp_c_{loc}"] = temp
                    forecast_by_time[t_][f"wind_ms_{loc}"] = wind
                    forecast_by_time[t_][f"wind_cubed_{loc}"] = wind ** 3
                break
            except Exception as e:
                print(f"  Live weather fetch attempt {attempt+1}/3 failed for {loc}: {e}")
                if attempt < 2:
                    time.sleep(10)
        time.sleep(1)
    return forecast_by_time


def build_target_row(target_time: pd.Timestamp, price_history: pd.DataFrame,
                     weather_forecast: dict, fingrid_latest: dict) -> dict:
    """Build a feature row for a FUTURE target_time: calendar features derived
    from target_time itself, price lags looked up from real history, weather
    from the live forecast, Fingrid from last known values."""
    row_df = pd.DataFrame({"timestamp": [target_time]})
    row_df = add_calendar_features(row_df)
    row = row_df.iloc[0].to_dict()

    lag24_time = target_time - pd.Timedelta(hours=24)
    lag168_time = target_time - pd.Timedelta(hours=168)
    m24 = price_history[price_history["timestamp"] == lag24_time]
    m168 = price_history[price_history["timestamp"] == lag168_time]
    row["price_lag_24h"] = m24["price_snt_kwh"].iloc[0] if len(m24) else np.nan
    row["price_lag_168h"] = m168["price_snt_kwh"].iloc[0] if len(m168) else np.nan

    window_start = target_time - pd.Timedelta(hours=25)
    window_end = target_time - pd.Timedelta(hours=1)
    window = price_history[(price_history["timestamp"] >= window_start) &
                           (price_history["timestamp"] <= window_end)]
    row["price_rolling_mean_24h"] = window["price_snt_kwh"].mean() if len(window) >= 20 else np.nan

    weather_row = weather_forecast.get(target_time, {})
    row.update(weather_row)
    for loc in OPEN_METEO_LOCATIONS:
        for col in (f"temp_c_{loc}", f"wind_ms_{loc}", f"wind_cubed_{loc}"):
            row.setdefault(col, np.nan)
    row.update(fingrid_latest)
    return row


def generate(feats: pd.DataFrame, models: dict, price_history: pd.DataFrame) -> pd.DataFrame:
    feats_sorted = feats.sort_values("timestamp")
    latest_price_time = feats_sorted["timestamp"].iloc[-1]
    made_at = pd.Timestamp.now("UTC")

    print("Fetching live weather forecast (Open-Meteo, no archive lag)...")
    weather_forecast = fetch_live_weather_forecast()
    print(f"  Got weather for {len(weather_forecast)} future hours")

    fingrid_cols = ["consumption_forecast_mw", "wind_forecast_mw", "nuclear_production_mw"]
    present_fingrid = [c for c in fingrid_cols if c in feats_sorted.columns]
    latest_fingrid = feats_sorted[present_fingrid].dropna().iloc[-1:].to_dict("records")
    latest_fingrid = latest_fingrid[0] if latest_fingrid else {}

    rows = []
    for h in HORIZONS_HOURS:
        model, feature_cols = models[h]
        target_time = latest_price_time + pd.Timedelta(hours=h)
        row = build_target_row(target_time, price_history, weather_forecast, latest_fingrid)
        X = pd.DataFrame([row])[feature_cols]
        pred = model.predict(X)[0]
        rows.append({
            "target_timestamp": target_time,
            "made_at": made_at,
            "horizon_hours": h,
            "predicted_price_snt_kwh": float(pred),
        })
        print(f"  N+{h//24}: target={target_time}, predicted={pred:.3f}")
    return pd.DataFrame(rows)


def freeze(pred_df: pd.DataFrame):
    if pred_df.empty:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            target_timestamp TEXT NOT NULL,
            made_at TEXT NOT NULL,
            horizon_hours INTEGER NOT NULL,
            predicted_price_snt_kwh REAL NOT NULL,
            PRIMARY KEY (target_timestamp, made_at)
        )
    """)
    written = 0
    for _, row in pred_df.iterrows():
        cur = conn.execute(
            "INSERT OR IGNORE INTO predictions "
            "(target_timestamp, made_at, horizon_hours, predicted_price_snt_kwh) "
            "VALUES (?, ?, ?, ?)",
            (row["target_timestamp"].isoformat(), row["made_at"].isoformat(),
             int(row["horizon_hours"]), row["predicted_price_snt_kwh"]),
        )
        written += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Frozen {written} new predictions.")


if __name__ == "__main__":
    feats_raw = pd.read_parquet(FEATURES_PATH)
    feats = build_features(feats_raw)
    price_history = pd.read_parquet("data/price_history_hourly.parquet")
    print(f"Loaded {len(feats)} rows, {len(feats.columns)} columns")
    models = train_full_models(feats)
    pred = generate(feats, models, price_history)
    print(pred.to_string(index=False))
    freeze(pred)
