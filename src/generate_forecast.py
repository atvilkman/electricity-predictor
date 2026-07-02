"""
generate_forecast.py — trains on data/features_full_hourly.parquet
so the model actually uses ALL wired data sources (calendar + lags +
weather + Fingrid consumption/wind), not just calendar + lags.
"""

import sqlite3
import pandas as pd
import lightgbm as lgb

from features import build_features, features_available_at_horizon

HORIZONS_HOURS = [24, 48, 72, 96, 120]
FEATURES_PATH = "data/features_full_hourly.parquet"
DB_PATH = "data/electricity.db"


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


def generate(feats: pd.DataFrame, models: dict) -> pd.DataFrame:
    feats_sorted = feats.sort_values("timestamp")
    # Anchor target timestamps to the latest known price, regardless of weather lag.
    latest_price_time = feats_sorted["timestamp"].iloc[-1]
    made_at = pd.Timestamp.now("UTC")
    rows = []
    for h in HORIZONS_HOURS:
        model, feature_cols = models[h]
        # Use the most recent row that has ALL required features. Weather archive
        # has a ~5-day lag, so this may be a few days behind the latest price row.
        complete = feats_sorted.dropna(subset=feature_cols)
        if complete.empty:
            print(f"  N+{h//24}: SKIPPED (no complete rows for features: {feature_cols})")
            continue
        X = complete.iloc[[-1]][feature_cols]
        lag_h = int((latest_price_time - complete.iloc[-1]["timestamp"]).total_seconds() / 3600)
        if lag_h > 0:
            print(f"  N+{h//24}: feature row is {lag_h}h old (weather archive lag)")
        pred = model.predict(X)[0]
        rows.append({
            "target_timestamp": latest_price_time + pd.Timedelta(hours=h),
            "made_at": made_at,
            "horizon_hours": h,
            "predicted_price_snt_kwh": float(pred),
        })
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
    print(f"Loaded {len(feats)} rows, {len(feats.columns)} columns")
    models = train_full_models(feats)
    pred = generate(feats, models)
    print(pred.to_string(index=False))
    freeze(pred)
