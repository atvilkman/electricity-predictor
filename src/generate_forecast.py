"""
generate_forecast.py — trains full-history models and freezes a real
forecast (N+1..N+5) into the predictions table.

v1 scope note: predicts 5 discrete points (24h, 48h, 72h, 96h, 120h ahead
of the latest known price row), matching the 5 horizon models from
train_predict.py. Not yet a full 120-point hourly curve.
"""

import sqlite3
import pandas as pd
import lightgbm as lgb

from features import build_features, features_available_at_horizon

HORIZONS_HOURS = [24, 48, 72, 96, 120]


def train_full_models(feats: pd.DataFrame) -> dict:
    """Train one model per horizon on ALL available history."""
    models = {}
    for h in HORIZONS_HOURS:
        feature_cols = [c for c in features_available_at_horizon(h) if c in feats.columns]
        df = feats.copy()
        df["target"] = df["price_snt_kwh"].shift(-h)
        usable = df.dropna(subset=feature_cols + ["target"])

        model = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=31, random_state=42, verbosity=-1,
        )
        model.fit(usable[feature_cols], usable["target"])
        models[h] = (model, feature_cols)
    return models


def generate_forecast(feats: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Predict N+1..N+5 from the latest known row's features."""
    latest_row = feats.sort_values("timestamp").iloc[[-1]]
    latest_time = latest_row["timestamp"].iloc[0]
    made_at = pd.Timestamp.now("UTC")

    rows = []
    for h in HORIZONS_HOURS:
        model, feature_cols = models[h]
        X = latest_row[feature_cols]
        if X.isna().any(axis=1).iloc[0]:
            print(f"Horizon {h}h: latest row missing required features, skipping")
            continue
        pred = model.predict(X)[0]
        rows.append({
            "target_timestamp": latest_time + pd.Timedelta(hours=h),
            "made_at": made_at,
            "horizon_hours": h,
            "predicted_price_snt_kwh": float(pred),
        })
    return pd.DataFrame(rows)


def freeze_predictions(pred_df: pd.DataFrame, db_path: str = "data/electricity.db"):
    """Write predictions, never overwriting an existing (target, made_at) pair."""
    if pred_df.empty:
        print("No predictions to freeze.")
        return
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
    rows_written = 0
    for _, row in pred_df.iterrows():
        cur = conn.execute(
            "INSERT OR IGNORE INTO predictions "
            "(target_timestamp, made_at, horizon_hours, predicted_price_snt_kwh) "
            "VALUES (?, ?, ?, ?)",
            (
                row["target_timestamp"].isoformat(),
                row["made_at"].isoformat(),
                int(row["horizon_hours"]),
                row["predicted_price_snt_kwh"],
            ),
        )
        rows_written += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Frozen {rows_written} new prediction row(s) into {db_path}")


if __name__ == "__main__":
    price_df = pd.read_parquet("data/price_history_hourly.parquet")
    feats = build_features(price_df)
    print(f"Training on {len(feats)} historical rows "
          f"(latest: {feats['timestamp'].max()})")

    models = train_full_models(feats)
    pred_df = generate_forecast(feats, models)

    print("\nGenerated forecast:")
    print(pred_df.to_string(index=False))

    freeze_predictions(pred_df)
