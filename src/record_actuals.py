"""
record_actuals.py — for every prediction whose target hour has passed,
look up the real price and write it to the actuals table. Unlocks the
Forecast vs Actual and Accuracy tabs. Idempotent (INSERT OR IGNORE).
"""

import sqlite3
import pandas as pd

DB_PATH = "data/electricity.db"
PRICE_HISTORY_PATH = "data/price_history_hourly.parquet"


def record_actuals():
    conn = sqlite3.connect(DB_PATH)
    preds = pd.read_sql("SELECT DISTINCT target_timestamp FROM predictions", conn)
    preds["target_timestamp"] = pd.to_datetime(preds["target_timestamp"], utc=True)
    prices = pd.read_parquet(PRICE_HISTORY_PATH)
    now_utc = pd.Timestamp.now("UTC")
    matured = preds[preds["target_timestamp"] <= now_utc]

    merged = matured.merge(
        prices[["timestamp", "price_snt_kwh"]],
        left_on="target_timestamp", right_on="timestamp", how="inner",
    )
    if merged.empty:
        print("No matured predictions with known actuals yet.")
        conn.close()
        return

    written = 0
    for _, row in merged.iterrows():
        cur = conn.execute(
            "INSERT OR IGNORE INTO actuals (target_timestamp, actual_price_snt_kwh) VALUES (?, ?)",
            (row["target_timestamp"].isoformat(), float(row["price_snt_kwh"])),
        )
        written += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Recorded {written} new actuals (of {len(merged)} matured predictions checked).")


if __name__ == "__main__":
    record_actuals()
