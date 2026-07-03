"""
generate_hourly_forecast.py — a single LightGBM model that takes
horizon_hours as an explicit feature, instead of 5 separate horizon-specific
models. Predicts at any hour offset (1-120h) for a real continuous hourly
forecast curve instead of 5 discrete daily points.
"""

import sqlite3
import numpy as np
import pandas as pd
import lightgbm as lgb

from features import build_features, FEATURE_AVAILABILITY_HOURS, add_calendar_features

FEATURES_PATH = "data/features_full_hourly.parquet"
DB_PATH = "data/electricity.db"
HORIZON_STEP_HOURS = 3
MAX_HORIZON_HOURS = 120

BASE_FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_holiday", "price_lag_24h", "price_lag_168h", "price_rolling_mean_24h",
    "temp_c_helsinki", "wind_ms_helsinki", "wind_cubed_helsinki",
    "temp_c_vaasa", "wind_ms_vaasa", "wind_cubed_vaasa",
    "consumption_forecast_mw", "wind_forecast_mw", "nuclear_production_mw",
]


def build_expanded_training_set(feats: pd.DataFrame) -> pd.DataFrame:
    horizons = list(range(HORIZON_STEP_HOURS, MAX_HORIZON_HOURS + 1, HORIZON_STEP_HOURS))
    feats = feats.sort_values("timestamp").reset_index(drop=True)
    price = feats.set_index("timestamp")["price_snt_kwh"]

    chunks = []
    for h in horizons:
        chunk = feats.copy()
        chunk["horizon_hours"] = h
        target_times = chunk["timestamp"] + pd.Timedelta(hours=h)
        chunk["target"] = target_times.map(price)

        for col, avail in FEATURE_AVAILABILITY_HOURS.items():
            if avail is not None and col in chunk.columns and h > avail:
                chunk[col] = np.nan

        chunks.append(chunk)

    expanded = pd.concat(chunks, ignore_index=True)
    return expanded.dropna(subset=["target"])


def train_hourly_model(feats: pd.DataFrame):
    expanded = build_expanded_training_set(feats)
    feature_cols = BASE_FEATURE_COLS + ["horizon_hours"]
    feature_cols = [c for c in feature_cols if c in expanded.columns]

    model = lgb.LGBMRegressor(
        n_estimators=400, learning_rate=0.05, max_depth=7,
        num_leaves=63, random_state=42, verbosity=-1,
    )
    model.fit(expanded[feature_cols], expanded["target"])
    print(f"Trained on {len(expanded)} expanded rows, {len(feature_cols)} features")
    return model, feature_cols


def build_target_row(target_time, horizon_h, price_history, weather_forecast, fingrid_latest):
    row_df = pd.DataFrame({"timestamp": [target_time]})
    row_df = add_calendar_features(row_df)
    row = row_df.iloc[0].to_dict()
    row["horizon_hours"] = horizon_h

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
    row.update(fingrid_latest)

    for col, avail in FEATURE_AVAILABILITY_HOURS.items():
        if avail is not None and horizon_h > avail:
            row[col] = np.nan

    return row


def generate_hourly_curve(feats, model, feature_cols, price_history,
                           weather_forecast, fingrid_latest, step_hours=1):
    feats_sorted = feats.sort_values("timestamp")
    latest_time = feats_sorted["timestamp"].iloc[-1]
    made_at = pd.Timestamp.now("UTC")

    rows = []
    for h in range(step_hours, MAX_HORIZON_HOURS + 1, step_hours):
        target_time = latest_time + pd.Timedelta(hours=h)
        row = build_target_row(target_time, h, price_history, weather_forecast, fingrid_latest)
        X = pd.DataFrame([row])[feature_cols]
        pred = model.predict(X)[0]
        rows.append({
            "target_timestamp": target_time,
            "made_at": made_at,
            "horizon_hours": h,
            "predicted_price_snt_kwh": float(pred),
        })
    return pd.DataFrame(rows)


def freeze_hourly(pred_df):
    if pred_df.empty:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hourly_predictions (
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
            "INSERT OR IGNORE INTO hourly_predictions "
            "(target_timestamp, made_at, horizon_hours, predicted_price_snt_kwh) "
            "VALUES (?, ?, ?, ?)",
            (row["target_timestamp"].isoformat(), row["made_at"].isoformat(),
             int(row["horizon_hours"]), row["predicted_price_snt_kwh"]),
        )
        written += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Frozen {written} hourly predictions.")


def fetch_live_weather_forecast():
    import time
    import requests
    OPEN_METEO_LOCATIONS = {"helsinki": (60.1699, 24.9384), "vaasa": (63.0960, 21.6158)}
    forecast_by_time = {}
    for loc, (lat, lon) in OPEN_METEO_LOCATIONS.items():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m,wind_speed_10m",
                   "forecast_days": 7, "timezone": "UTC"}
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
    return forecast_by_time


def run():
    feats_raw = pd.read_parquet(FEATURES_PATH)
    feats = build_features(feats_raw)
    price_history = pd.read_parquet("data/price_history_hourly.parquet")
    print(f"Loaded {len(feats)} rows")

    model, feature_cols = train_hourly_model(feats)

    print("Fetching live weather forecast...")
    weather_forecast = fetch_live_weather_forecast()
    print(f"  Got weather for {len(weather_forecast)} future hours")

    feats_sorted = feats.sort_values("timestamp")
    latest_fingrid = feats_sorted[["consumption_forecast_mw", "wind_forecast_mw",
                                     "nuclear_production_mw"]].dropna().iloc[-1:].to_dict("records")
    latest_fingrid = latest_fingrid[0] if latest_fingrid else {}

    curve = generate_hourly_curve(feats, model, feature_cols, price_history,
                                    weather_forecast, latest_fingrid, step_hours=1)
    print(f"Generated {len(curve)} hourly predictions")
    print(curve.head(5).to_string(index=False))
    freeze_hourly(curve)


if __name__ == "__main__":
    run()
