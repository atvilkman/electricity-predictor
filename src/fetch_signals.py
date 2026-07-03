"""
fetch_signals.py — pulls the "Signals" KPI data sources: Syke hydrology
(snow water equivalent), JAO transmission capacity, Open-Meteo solar
radiation + neighboring-country wind + demand-pressure temperature, and
Fingrid nuclear availability. Writes data/signals_snapshot.json.
All sources are free/keyless.
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests

OUT_PATH = "data/signals_snapshot.json"

OPEN_METEO_LOCATIONS = {
    "helsinki": (60.1699, 24.9384),
    "vaasa": (63.0960, 21.6158),
    "stockholm": (59.3293, 18.0686),
    "copenhagen": (55.6761, 12.5683),
    "berlin": (52.5200, 13.4050),
    "tallinn": (59.4370, 24.7536),
}


def fetch_openmeteo_signals():
    now = pd.Timestamp.now("UTC")

    forecast_wind = {}
    forecast_solar = None
    forecast_temp = None
    for loc, (lat, lon) in OPEN_METEO_LOCATIONS.items():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "wind_speed_10m,shortwave_radiation,temperature_2m",
            "forecast_days": 2, "timezone": "UTC",
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            h = r.json()["hourly"]
            times = pd.to_datetime(h["time"], utc=True)
            df = pd.DataFrame({"t": times, "wind": h["wind_speed_10m"],
                                "solar": h["shortwave_radiation"],
                                "temp": h["temperature_2m"]})
            next24 = df[(df["t"] >= now) & (df["t"] < now + pd.Timedelta(hours=24))]
            forecast_wind[loc] = next24["wind"].mean()
            if loc == "helsinki":
                forecast_solar = next24["solar"].mean()
                forecast_temp = next24["temp"].mean()
        except Exception as e:
            print(f"  Open-Meteo forecast failed for {loc}: {e}")
            forecast_wind[loc] = None
        time.sleep(0.5)

    baseline_wind = {}
    baseline_solar = None
    baseline_temp = None
    start = (now - pd.Timedelta(days=35)).strftime("%Y-%m-%d")
    end = (now - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    for loc, (lat, lon) in OPEN_METEO_LOCATIONS.items():
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "wind_speed_10m,shortwave_radiation,temperature_2m",
            "start_date": start, "end_date": end, "timezone": "UTC",
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            h = r.json()["hourly"]
            baseline_wind[loc] = pd.Series(h["wind_speed_10m"]).mean()
            if loc == "helsinki":
                baseline_solar = pd.Series(h["shortwave_radiation"]).mean()
                baseline_temp = pd.Series(h["temperature_2m"]).mean()
        except Exception as e:
            print(f"  Open-Meteo archive failed for {loc}: {e}")
            baseline_wind[loc] = None
        time.sleep(0.5)

    wind_now = pd.Series(forecast_wind).mean()
    wind_baseline = pd.Series(baseline_wind).mean()

    return {
        "wind": {"value_ms": round(float(wind_now), 2) if pd.notna(wind_now) else None,
                 "baseline_ms": round(float(wind_baseline), 2) if pd.notna(wind_baseline) else None},
        "solar": {"value_wm2": round(float(forecast_solar), 1) if forecast_solar is not None else None,
                  "baseline_wm2": round(float(baseline_solar), 1) if baseline_solar is not None else None},
        "demand": {"value_c": round(float(forecast_temp), 1) if forecast_temp is not None else None,
                   "baseline_c": round(float(baseline_temp), 1) if baseline_temp is not None else None},
    }


NUCLEAR_INSTALLED_MW = 4394  # OL1 890 + OL2 890 + OL3 1600 + Loviisa1 507 + Loviisa2 507


def fetch_nuclear_availability():
    try:
        feats = pd.read_parquet("data/features_full_hourly.parquet")
        latest = feats.dropna(subset=["nuclear_production_mw"]).sort_values("timestamp")
        if latest.empty:
            return {"value_mw": None, "pct_of_capacity": None}
        val = float(latest["nuclear_production_mw"].iloc[-1])
        return {
            "value_mw": round(val, 0),
            "pct_of_capacity": round(val / NUCLEAR_INSTALLED_MW * 100, 1),
        }
    except Exception as e:
        print(f"  Nuclear availability read failed: {e}")
        return {"value_mw": None, "pct_of_capacity": None}


SYKE_BASE = "https://rajapinnat.ymparisto.fi/api/Hydrologiarajapinta/1.2/odata"


def fetch_syke_snow_signal():
    """Aggregate all LumiAlue stations for the latest date as a Finland-wide SWE mean.
    No single 'koko maa' station exists — must compute from all individual catchment readings."""
    try:
        hdrs = {"Accept": "application/json"}
        lumi_url = f"{SYKE_BASE}/LumiAlue"

        # Latest date's data (all stations, ordered desc by date)
        r = requests.get(lumi_url, params={"$top": 500, "$orderby": "Aika desc"}, headers=hdrs, timeout=30)
        r.raise_for_status()
        rows = r.json().get("value", [])
        if not rows:
            return {"value_mm": None, "baseline_mm": None, "note": "no_data"}

        latest_date = rows[0]["Aika"]
        latest_vals = [float(row["Arvo"]) for row in rows
                       if row.get("Aika") == latest_date and row.get("Arvo") is not None]
        latest_val = sum(latest_vals) / len(latest_vals) if latest_vals else None
        print(f"  Syke: {len(latest_vals)} stations on {latest_date}, mean SWE={latest_val:.1f} mm")

        # 5-year baseline: same calendar week, prior years
        baseline_val = None
        if latest_date:
            dt = pd.Timestamp(latest_date)
            week = dt.isocalendar().week
            baseline_vals = []
            for yr in [dt.year - i for i in range(1, 6)]:
                target = pd.Timestamp.fromisocalendar(int(yr), int(week), 1)
                w_start = (target - pd.Timedelta(days=3)).strftime("%Y-%m-%dT00:00:00")
                w_end = (target + pd.Timedelta(days=3)).strftime("%Y-%m-%dT00:00:00")
                try:
                    rr = requests.get(lumi_url, headers=hdrs, timeout=30, params={
                        "$filter": f"Aika ge datetime'{w_start}' and Aika le datetime'{w_end}'",
                        "$top": 1000,
                    })
                    rr.raise_for_status()
                    yr_rows = rr.json().get("value", [])
                    yr_vals = [float(row["Arvo"]) for row in yr_rows if row.get("Arvo") is not None]
                    if yr_vals:
                        baseline_vals.append(sum(yr_vals) / len(yr_vals))
                except Exception:
                    pass
                time.sleep(0.3)
            if baseline_vals:
                baseline_val = sum(baseline_vals) / len(baseline_vals)

        return {
            "value_mm": round(float(latest_val), 1) if latest_val is not None else None,
            "baseline_mm": round(float(baseline_val), 1) if baseline_val is not None else None,
            "as_of": latest_date,
        }
    except Exception as e:
        print(f"  Syke fetch failed: {e}")
        return {"value_mm": None, "baseline_mm": None, "note": "fetch_failed"}


def fetch_jao_transmission():
    try:
        from jao import JaoPublicationToolPandasNordics
        client = JaoPublicationToolPandasNordics()
        tomorrow = (pd.Timestamp.now("UTC") + pd.Timedelta(days=1)).normalize()

        results = {}
        pairs = [("FI", "SE1"), ("SE1", "FI"), ("FI", "SE3"), ("SE3", "FI"),
                  ("FI", "EE"), ("EE", "FI")]
        for from_z, to_z in pairs:
            try:
                df = client.query_maxbex(tomorrow, from_zone=from_z, to_zone=to_z)
                key = f"{from_z}->{to_z}"
                if df is not None and len(df) > 0:
                    numeric_cols = df.select_dtypes(include="number").columns
                    results[key] = round(float(df[numeric_cols[0]].mean()), 1) if len(numeric_cols) else None
                else:
                    results[key] = None
            except Exception as e:
                print(f"  JAO {from_z}->{to_z} failed: {e}")
                results[f"{from_z}->{to_z}"] = None
        return results
    except Exception as e:
        print(f"  JAO client failed entirely: {e}")
        return {}


def build_snapshot():
    print("Fetching Open-Meteo wind/solar/demand signals...")
    om = fetch_openmeteo_signals()

    print("Fetching Syke hydrology signal...")
    syke = fetch_syke_snow_signal()

    print("Fetching JAO transmission capacity...")
    jao = fetch_jao_transmission()

    print("Reading nuclear availability from Fingrid data...")
    nuclear = fetch_nuclear_availability()

    return {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "wind": om["wind"],
        "solar": om["solar"],
        "demand": om["demand"],
        "hydro": syke,
        "transmission": jao,
        "nuclear": nuclear,
    }


if __name__ == "__main__":
    snap = build_snapshot()
    Path("data").mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(snap, f, indent=2)
    print(f"\nWritten: {OUT_PATH}")
    print(json.dumps(snap, indent=2))
