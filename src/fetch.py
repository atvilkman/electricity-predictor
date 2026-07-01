"""
fetch.py — Phase 2: Data Ingestion

Currently implements: ENTSO-E historical price loading (BZN|FI).
Next additions (same file): porssisahko near-term, Fingrid grid data,
Open-Meteo weather.
"""

import re
import sys
import glob
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
