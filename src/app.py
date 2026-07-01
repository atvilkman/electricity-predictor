"""
app.py — Phase 5: Streamlit Dashboard

Three tabs:
  1. Forecast          — known 36h + rolling 5-day predicted window
  2. Forecast vs Actual — frozen past predictions against real outcomes
  3. Accuracy           — model MAE vs naive-week baseline, per horizon

Reads from:
  - data/price_history_hourly.parquet (historical known prices)
  - data/electricity.db (predictions + actuals — the freeze mechanism)
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="FI Electricity Price Forecast", layout="wide")

DB_PATH = "data/electricity.db"
PRICE_HISTORY_PATH = "data/price_history_hourly.parquet"

CHEAP_THRESHOLD = 2.0
EXPENSIVE_THRESHOLD = 15.0


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


def render_forecast_tab():
    st.subheader("Rolling forecast: known 36h + predicted 5 days")

    history = load_price_history()
    preds, _ = load_predictions_and_actuals()

    if history.empty and preds.empty:
        st.info(
            "No data yet. Run `python src/fetch.py` and `python src/train_predict.py` "
            "to populate historical prices and generate the first forecast."
        )
        return

    now = pd.Timestamp.utcnow()
    recent_known = history[history["timestamp"] >= now - pd.Timedelta(hours=36)]
    latest_preds = preds[preds["made_at"] == preds["made_at"].max()] if not preds.empty else preds

    fig = go.Figure()

    if not recent_known.empty:
        fig.add_trace(go.Scatter(
            x=recent_known["timestamp"], y=recent_known["price_snt_kwh"],
            mode="lines", name="Known (actual)",
            line=dict(color="#1f77b4", width=2),
        ))

    if not latest_preds.empty:
        latest_preds = latest_preds.sort_values("target_timestamp")
        fig.add_trace(go.Scatter(
            x=latest_preds["target_timestamp"], y=latest_preds["predicted_price_snt_kwh"],
            mode="lines", name="Forecast",
            line=dict(color="#1f77b4", width=2, dash="dash"),
        ))
    else:
        st.warning("No frozen predictions yet — the daily pipeline hasn't produced a forecast run.")

    fig.add_hline(y=CHEAP_THRESHOLD, line_dash="dot", line_color="green",
                   annotation_text="Cheap threshold")
    fig.add_hline(y=EXPENSIVE_THRESHOLD, line_dash="dot", line_color="red",
                   annotation_text="Expensive threshold")

    fig.update_layout(
        xaxis_title="Time (UTC)", yaxis_title="Price (snt/kWh)",
        hovermode="x unified", height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

    if not recent_known.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Cheapest recent hour", f"{recent_known['price_snt_kwh'].min():.2f} snt/kWh")
        col2.metric("Average", f"{recent_known['price_snt_kwh'].mean():.2f} snt/kWh")
        col3.metric("Most expensive recent hour", f"{recent_known['price_snt_kwh'].max():.2f} snt/kWh")


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

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged["target_timestamp"], y=merged["actual_price_snt_kwh"],
        mode="lines+markers", name="Actual", line=dict(color="#1f77b4"),
    ))
    fig.add_trace(go.Scatter(
        x=merged["target_timestamp"], y=merged["predicted_price_snt_kwh"],
        mode="lines+markers", name="Predicted (frozen)", line=dict(color="#ff7f0e", dash="dash"),
    ))
    fig.update_layout(xaxis_title="Time (UTC)", yaxis_title="Price (snt/kWh)",
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
    st.caption(f"Last loaded: {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    tab1, tab2, tab3 = st.tabs(["Forecast", "Forecast vs Actual", "Accuracy"])
    with tab1:
        render_forecast_tab()
    with tab2:
        render_forecast_vs_actual_tab()
    with tab3:
        render_accuracy_tab()


if __name__ == "__main__":
    main()
