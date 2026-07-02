"""
app.py — Phase 5: Streamlit Dashboard

Three tabs:
  1. Forecast          — known 36h + rolling 5-day predicted window,
                          with a "typical error" band and labeled N+1..N+5 points
  2. Forecast vs Actual — frozen past predictions against real outcomes
  3. Accuracy           — model MAE vs naive-week baseline, per horizon

Reads from:
  - data/price_history_hourly.parquet (historical known prices)
  - data/electricity.db (predictions + actuals — the freeze mechanism)
  - data/model_validation_results.parquet (per-horizon MAE, for the error band)
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="FI Electricity Price Forecast", layout="wide")

DB_PATH = "data/electricity.db"
PRICE_HISTORY_PATH = "data/price_history_hourly.parquet"
VALIDATION_RESULTS_PATH = "data/model_validation_results.parquet"

CHEAP_THRESHOLD = 2.0
EXPENSIVE_THRESHOLD = 15.0

LOCAL_TZ = "Europe/Helsinki"


def to_local(series):
    """Convert a UTC timestamp series to Europe/Helsinki for display."""
    return series.dt.tz_convert(LOCAL_TZ)


@st.cache_data(ttl=600)
def load_price_history() -> pd.DataFrame:
    if not Path(PRICE_HISTORY_PATH).exists():
        return pd.DataFrame(columns=["timestamp", "price_snt_kwh"])
    df = pd.read_parquet(PRICE_HISTORY_PATH)
    return df[["timestamp", "price_snt_kwh"]]


@st.cache_data(ttl=600)
def load_predictions_and_actuals():
    if not Path(DB_PATH).exists():
        empty = pd.DataFrame(columns=["target_timestamp", "made_at", "horizon_hours", "predicted_price_snt_kwh"])
        return empty, pd.DataFrame(columns=["target_timestamp", "actual_price_snt_kwh"])
    conn = sqlite3.connect(DB_PATH)
    preds = pd.read_sql("SELECT * FROM predictions", conn)
    actuals = pd.read_sql("SELECT * FROM actuals", conn)
    conn.close()
    if not preds.empty:
        preds["target_timestamp"] = pd.to_datetime(preds["target_timestamp"], utc=True)
        preds["made_at"] = pd.to_datetime(preds["made_at"], utc=True)
    if not actuals.empty:
        actuals["target_timestamp"] = pd.to_datetime(actuals["target_timestamp"], utc=True)
    return preds, actuals


@st.cache_data(ttl=600)
def load_mae_by_horizon() -> dict:
    """Return {horizon_hours: model_mae_snt_kwh} from the last validation run."""
    if not Path(VALIDATION_RESULTS_PATH).exists():
        return {}
    df = pd.read_parquet(VALIDATION_RESULTS_PATH)
    return dict(zip(df["horizon_hours"], df["model_mae_snt_kwh"]))


def render_forecast_tab():
    st.subheader("Rolling forecast: known 36h + predicted 5 days")

    history = load_price_history()
    preds, _ = load_predictions_and_actuals()
    mae_by_horizon = load_mae_by_horizon()

    if history.empty and preds.empty:
        st.info(
            "No data yet. Run `python src/fetch.py` and `python src/train_predict.py` "
            "to populate historical prices and generate the first forecast."
        )
        return

    now_utc = pd.Timestamp.now("UTC")
    now_local = now_utc.tz_convert(LOCAL_TZ)
    now_str = now_local.strftime("%Y-%m-%d %H:%M:%S")
    now_label = now_local.strftime("%d %b %H:%M")

    recent_known = history[history["timestamp"] >= now_utc - pd.Timedelta(hours=36)].copy()
    latest_preds = (preds[preds["made_at"] == preds["made_at"].max()].copy()
                     if not preds.empty else preds)

    fig = go.Figure()

    if not recent_known.empty:
        recent_known["timestamp_local"] = to_local(recent_known["timestamp"])
        fig.add_trace(go.Scatter(
            x=recent_known["timestamp_local"], y=recent_known["price_snt_kwh"],
            mode="lines", name="Known (actual)",
            line=dict(color="#1f77b4", width=2),
        ))

    if not latest_preds.empty:
        latest_preds = latest_preds.sort_values("target_timestamp")
        latest_preds["timestamp_local"] = to_local(latest_preds["target_timestamp"])
        latest_preds["horizon_label"] = "N+" + (latest_preds["horizon_hours"] // 24).astype(str)
        latest_preds["mae"] = latest_preds["horizon_hours"].map(mae_by_horizon)

        band = latest_preds.dropna(subset=["mae"])
        if not band.empty:
            upper = band["predicted_price_snt_kwh"] + band["mae"]
            lower = (band["predicted_price_snt_kwh"] - band["mae"]).clip(lower=0)
            fig.add_trace(go.Scatter(
                x=list(band["timestamp_local"]) + list(band["timestamp_local"][::-1]),
                y=list(upper) + list(lower[::-1]),
                fill="toself", fillcolor="rgba(31,119,180,0.15)",
                line=dict(width=0), hoverinfo="skip",
                name="Typical historical error range",
            ))

        fig.add_trace(go.Scatter(
            x=latest_preds["timestamp_local"], y=latest_preds["predicted_price_snt_kwh"],
            mode="lines+markers+text", name="Forecast",
            line=dict(color="#1f77b4", width=1.5, dash="dash"),
            marker=dict(size=9, color="#1f77b4"),
            text=latest_preds["horizon_label"], textposition="top center",
            textfont=dict(size=11, color="#1f77b4"),
        ))
    else:
        st.warning("No frozen predictions yet — the daily pipeline hasn't produced a forecast run.")

    if not recent_known.empty:
        known_before_now = recent_known[recent_known["timestamp"] <= now_utc]
        if not known_before_now.empty:
            current_row = known_before_now.iloc[-1]
            fig.add_trace(go.Scatter(
                x=[current_row["timestamp_local"]], y=[current_row["price_snt_kwh"]],
                mode="markers+text", name="Current price",
                marker=dict(size=14, color="#1f77b4", line=dict(color="white", width=2)),
                text=[f"  {current_row['price_snt_kwh']:.2f} snt/kWh"],
                textposition="middle right", textfont=dict(size=13, color="#1f77b4"),
                showlegend=False, cliponaxis=False,
            ))

    fig.add_shape(
        type="line", x0=now_str, x1=now_str, y0=0, y1=1, yref="paper",
        line=dict(color="gray", width=1.5, dash="dot"),
    )
    fig.add_annotation(
        x=now_str, y=0.02, yref="paper", text=now_label, showarrow=False,
        textangle=-90, font=dict(color="gray", size=11),
        bgcolor="white", xshift=10, yanchor="bottom",
    )

    fig.add_hline(y=CHEAP_THRESHOLD, line_dash="dot", line_color="green",
                   annotation_text="Cheap threshold", annotation_position="top left")
    fig.add_hline(y=EXPENSIVE_THRESHOLD, line_dash="dot", line_color="red",
                   annotation_text="Expensive threshold", annotation_position="top left")

    fig.update_layout(
        xaxis_title="Time (local, Europe/Helsinki)", yaxis_title="Price (snt/kWh)",
        hovermode="x unified", height=480,
    )
    st.plotly_chart(fig, use_container_width=True)

    if mae_by_horizon:
        st.caption(
            "Shaded band = typical historical error for that horizon "
            "(mean absolute error from backtesting), not a statistical confidence interval."
        )

    if not recent_known.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Cheapest hour (current 36h window)", f"{recent_known['price_snt_kwh'].min():.2f} snt/kWh")
        col2.metric("Average (current 36h window)", f"{recent_known['price_snt_kwh'].mean():.2f} snt/kWh")
        col3.metric("Most expensive hour (current 36h window)", f"{recent_known['price_snt_kwh'].max():.2f} snt/kWh")


def render_forecast_vs_actual_tab():
    st.subheader("Frozen forecasts vs what actually happened")

    preds, actuals = load_predictions_and_actuals()

    if preds.empty or actuals.empty:
        st.info(
            "Not enough history yet. This view fills in as daily forecasts "
            "'graduate' into known actuals — check back after a few days of runs."
        )
        return

    merged = preds.merge(actuals, on="target_timestamp", how="inner")
    if merged.empty:
        st.info("No frozen predictions have a matching actual yet.")
        return

    merged = merged.sort_values("target_timestamp")
    merged["timestamp_local"] = to_local(merged["target_timestamp"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged["timestamp_local"], y=merged["actual_price_snt_kwh"],
        mode="lines+markers", name="Actual", line=dict(color="#1f77b4"),
    ))
    fig.add_trace(go.Scatter(
        x=merged["timestamp_local"], y=merged["predicted_price_snt_kwh"],
        mode="lines+markers", name="Predicted (frozen)", line=dict(color="#ff7f0e", dash="dash"),
    ))
    fig.update_layout(xaxis_title="Time (local, Europe/Helsinki)", yaxis_title="Price (snt/kWh)",
                       hovermode="x unified", height=450)
    st.plotly_chart(fig, use_container_width=True)


def render_accuracy_tab():
    st.subheader("Accuracy: model vs naive-week baseline, by horizon")

    preds, actuals = load_predictions_and_actuals()

    if preds.empty or actuals.empty:
        st.info(
            "No scored predictions yet. Accuracy fills in once daily forecasts "
            "graduate into known actuals — this needs several days of automated runs."
        )
        return

    merged = preds.merge(actuals, on="target_timestamp", how="inner")
    if merged.empty:
        st.info("No frozen predictions have a matching actual yet.")
        return

    merged["abs_error"] = (merged["predicted_price_snt_kwh"] - merged["actual_price_snt_kwh"]).abs()
    by_horizon = merged.groupby("horizon_hours")["abs_error"].mean().reset_index()
    by_horizon["horizon_label"] = "N+" + (by_horizon["horizon_hours"] // 24).astype(str)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=by_horizon["horizon_label"], y=by_horizon["abs_error"],
        name="Model MAE (snt/kWh)", marker_color="#1f77b4",
    ))
    fig.update_layout(xaxis_title="Horizon", yaxis_title="MAE (snt/kWh)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    n_days = (merged["target_timestamp"].max() - merged["target_timestamp"].min()).days
    st.caption(f"Based on {len(merged)} scored predictions across {n_days} days of history.")


def main():
    st.title("Finnish Electricity Spot-Price Forecast")
    local_now = pd.Timestamp.now("UTC").tz_convert(LOCAL_TZ)
    st.caption(f"Last loaded: {local_now.strftime('%Y-%m-%d %H:%M %Z')}")
    st.caption("Prices shown are raw wholesale spot prices (excl. ALV / VAT and any retailer margin or transfer fees).")

    tab1, tab2, tab3 = st.tabs(["Forecast", "Forecast vs Actual", "Accuracy"])
    with tab1:
        render_forecast_tab()
    with tab2:
        render_forecast_vs_actual_tab()
    with tab3:
        render_accuracy_tab()


if __name__ == "__main__":
    main()
