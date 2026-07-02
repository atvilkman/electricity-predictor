"""
features.py — Phase 3: Feature Engineering

Builds model-ready features from the merged hourly data (price + weather +
grid). Critically, every feature is tagged with the maximum horizon at which
it is genuinely available, so the model can be trained "direct multi-horizon"
without leaking future information into short-horizon predictions.
"""

import numpy as np
import pandas as pd
import holidays

FI_HOLIDAYS = holidays.Finland()

FEATURE_AVAILABILITY_HOURS = {
    "hour_sin": None,
    "hour_cos": None,
    "dow_sin": None,
    "dow_cos": None,
    "month_sin": None,
    "month_cos": None,
    "is_holiday": None,
    "price_lag_24h": None,
    "price_lag_168h": None,
    "price_rolling_mean_24h": None,
    "temp_c_helsinki": 240,
    "wind_ms_helsinki": 240,
    "wind_cubed_helsinki": 240,
    "temp_c_vaasa": 240,
    "wind_ms_vaasa": 240,
    "wind_cubed_vaasa": 240,
    "consumption_forecast_mw": 72,
    "wind_forecast_mw": 36,
    "nuclear_production_mw": 48,   # Fingrid real-time-ish; treat as short-horizon only
}


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add cyclically-encoded hour/day-of-week/month + Finnish holiday flag."""
    df = df.copy()
    ts_local = df["timestamp"].dt.tz_convert("Europe/Helsinki")

    hour = ts_local.dt.hour
    dow = ts_local.dt.dayofweek
    month = ts_local.dt.month

    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    df["is_holiday"] = ts_local.dt.date.map(lambda d: d in FI_HOLIDAYS).astype(int)

    return df


def add_price_lags(df: pd.DataFrame, price_col: str = "price_snt_kwh") -> pd.DataFrame:
    """Add 24h/168h price lags and a 24h rolling mean. Requires hourly, sorted, no gaps."""
    df = df.copy()
    df["price_lag_24h"] = df[price_col].shift(24)
    df["price_lag_168h"] = df[price_col].shift(168)
    df["price_rolling_mean_24h"] = df[price_col].shift(1).rolling(24, min_periods=24).mean()
    return df


def add_wind_cubed(df: pd.DataFrame) -> pd.DataFrame:
    """Add wind^3 columns for each wind speed column present."""
    df = df.copy()
    for col in list(df.columns):
        if col.startswith("wind_ms_"):
            loc = col.replace("wind_ms_", "")
            df[f"wind_cubed_{loc}"] = df[col] ** 3
    return df


def build_features(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full feature pipeline for the historical price series.
    price_df must have columns: timestamp (UTC, hourly, sorted), price_snt_kwh.
    Weather/grid columns, if present, pass through untouched (wind_cubed added).
    """
    df = price_df.sort_values("timestamp").reset_index(drop=True)
    df = add_calendar_features(df)
    df = add_price_lags(df)
    df = add_wind_cubed(df)
    return df


def features_available_at_horizon(horizon_hours: int) -> list[str]:
    """Return the list of feature names usable when predicting this far ahead."""
    usable = []
    for feat, max_horizon in FEATURE_AVAILABILITY_HOURS.items():
        if max_horizon is None or horizon_hours <= max_horizon:
            usable.append(feat)
    return usable


if __name__ == "__main__":
    price_df = pd.read_parquet("data/price_history_hourly.parquet")
    feats = build_features(price_df)

    print(f"Rows: {len(feats)}")
    print(f"Columns: {list(feats.columns)}")
    print()
    print("NaN counts (expected: 24, 168, 24):")
    print(feats[["price_lag_24h", "price_lag_168h", "price_rolling_mean_24h"]].isna().sum())
    print()
    print("Features available at N+1 (24h horizon):", features_available_at_horizon(24))
    print()
    print("Features available at N+5 (120h horizon):", features_available_at_horizon(120))

    feats.to_parquet("data/features_hourly.parquet", index=False)
    print("\nWritten: data/features_hourly.parquet")
