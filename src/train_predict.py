"""
train_predict.py — Phase 4: Model & Freezing

Direct multi-horizon LightGBM forecaster. A separate model is trained per
horizon (N+1..N+5 days = 24/48/72/96/120 hours ahead), each using only the
features genuinely available at that lead time (see features.py's
FEATURE_AVAILABILITY_HOURS).

Also implements the freeze mechanism: predictions are written once
(target_timestamp, made_at) and never overwritten, so accuracy can later be
scored honestly against real outcomes.
"""

import sqlite3
import numpy as np
import pandas as pd
import lightgbm as lgb

from features import build_features, features_available_at_horizon

HORIZONS_HOURS = [24, 48, 72, 96, 120]  # N+1 .. N+5


def chronological_split(df: pd.DataFrame, val_days: int = 60):
    """Split by time, never shuffle. Last val_days become validation."""
    cutoff = df["timestamp"].max() - pd.Timedelta(days=val_days)
    train = df[df["timestamp"] <= cutoff].copy()
    val = df[df["timestamp"] > cutoff].copy()
    return train, val


def make_horizon_dataset(df: pd.DataFrame, horizon_hours: int, feature_cols: list[str]):
    """Build X, y for a given horizon: y = price `horizon_hours` ahead of each row."""
    df = df.copy()
    df["target"] = df["price_snt_kwh"].shift(-horizon_hours)
    # Only drop rows missing the target. LightGBM handles NaN in features natively.
    usable = df.dropna(subset=["target"])
    return usable[feature_cols], usable["target"], usable["timestamp"]


def naive_week_baseline(df: pd.DataFrame, horizon_hours: int) -> pd.Series:
    """Naive baseline: predicted price = actual price 168h (1 week) before the target hour."""
    price_series = df.set_index("timestamp")["price_snt_kwh"]
    target_times = df["timestamp"] + pd.Timedelta(hours=horizon_hours)
    lookup_times = target_times - pd.Timedelta(hours=168)
    return lookup_times.map(price_series)


def train_and_evaluate(feats: pd.DataFrame) -> pd.DataFrame:
    """Train one model per horizon, evaluate MAE vs naive-week baseline."""
    train_df, val_df = chronological_split(feats, val_days=60)
    results = []
    models = {}

    for h in HORIZONS_HOURS:
        feature_cols = [c for c in features_available_at_horizon(h)
                         if c in feats.columns]

        X_train, y_train, _ = make_horizon_dataset(train_df, h, feature_cols)
        X_val, y_val, val_ts = make_horizon_dataset(val_df, h, feature_cols)

        if len(X_train) < 100 or len(X_val) < 20:
            print(f"Horizon {h}h: insufficient data, skipping")
            continue

        model = lgb.LGBMRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            random_state=42,
            verbosity=-1,
        )
        model.fit(X_train, y_train)
        models[h] = model

        pred = model.predict(X_val)
        model_mae = np.mean(np.abs(pred - y_val.values))

        naive_pred = naive_week_baseline(val_df, h).loc[X_val.index]
        valid_mask = naive_pred.notna()
        naive_mae = np.mean(np.abs(naive_pred[valid_mask].values - y_val[valid_mask].values))

        results.append({
            "horizon_hours": h,
            "horizon_label": f"N+{h//24}",
            "n_train": len(X_train),
            "n_val": len(X_val),
            "model_mae_snt_kwh": round(model_mae, 3),
            "naive_week_mae_snt_kwh": round(naive_mae, 3),
            "beats_naive": model_mae < naive_mae,
        })

    return pd.DataFrame(results), models


def init_db(db_path: str = "data/electricity.db"):
    """Create the immutable predictions + actuals tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            target_timestamp TEXT NOT NULL,
            made_at TEXT NOT NULL,
            horizon_hours INTEGER NOT NULL,
            predicted_price_snt_kwh REAL NOT NULL,
            PRIMARY KEY (target_timestamp, made_at)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS actuals (
            target_timestamp TEXT PRIMARY KEY,
            actual_price_snt_kwh REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


if __name__ == "__main__":
    feats_raw = pd.read_parquet("data/features_full_hourly.parquet")
    feats = build_features(feats_raw)

    print(f"Total feature rows: {len(feats)}")
    print(f"Date range: {feats['timestamp'].min()} -> {feats['timestamp'].max()}")
    print()

    results_df, models = train_and_evaluate(feats)
    print("=== Model vs Naive-Week Baseline (validation set) ===")
    print(results_df.to_string(index=False))
    print()

    n_beats = results_df["beats_naive"].sum()
    print(f"Model beats naive-week baseline at {n_beats}/{len(results_df)} horizons.")

    conn = init_db()
    conn.close()
    print("\nDB initialized: data/electricity.db (predictions + actuals tables)")

    results_df.to_parquet("data/model_validation_results.parquet", index=False)
    print("Written: data/model_validation_results.parquet")
