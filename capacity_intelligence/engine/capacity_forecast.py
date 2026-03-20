"""Capacity Intelligence forecasting engine.

All heavy computation lives here; app.py calls these functions and
renders the results.  No Streamlit imports allowed in this file.
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Scenario event multipliers (applied multiplicatively)
# ---------------------------------------------------------------------------
SCENARIO_MULTIPLIERS: Dict[str, float] = {
    "townhall": 1.20,
    "leadership_visit": 1.15,
    "weather_alert": 0.70,
    "traffic_disruption": 0.80,
    "mandatory_holiday": 0.10,
    "optional_holiday": 0.60,
    "us_holiday": 0.75,
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _total_capacity(df: pd.DataFrame) -> int:
    """Sum capacity across all unique entities.

    Tower-aware: when tower_id column is present each tower row carries its own
    capacity, so we group by tower_id.  Falls back to building_id for flat data.
    """
    if "tower_id" in df.columns:
        return int(df.groupby("tower_id")["capacity"].first().sum())
    return int(df.groupby("building_id")["capacity"].first().sum())


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def filter_df(
    daily_df: pd.DataFrame,
    buildings: Optional[List[str]] = None,
    cities: Optional[List[str]] = None,
    lobs: Optional[List[str]] = None,
) -> pd.DataFrame:
    df = daily_df
    if buildings:
        df = df[df["building_id"].isin(buildings)]
    if cities:
        df = df[df["city"].isin(cities)]
    if lobs:
        df = df[df["lob"].isin(lobs)]
    return df


def get_horizon_df(daily_df: pd.DataFrame, horizon_days: int = 30) -> pd.DataFrame:
    today = pd.Timestamp(date.today())
    end = today + pd.Timedelta(days=horizon_days)
    return daily_df[(daily_df["date"] >= today) & (daily_df["date"] < end)]


# ---------------------------------------------------------------------------
# Short-term KPIs
# ---------------------------------------------------------------------------

def compute_portfolio_kpis(
    daily_df: pd.DataFrame,
    horizon_days: int = 30,
    metric: str = "peak",
) -> dict:
    """Returns peak_footfall, avg_footfall, buildings_above_90, buildings_below_60, total_capacity."""
    df = get_horizon_df(daily_df, horizon_days)
    if df.empty:
        return {
            "peak_footfall": 0,
            "avg_footfall": 0,
            "buildings_above_90": 0,
            "buildings_below_60": 0,
            "total_capacity": 0,
        }

    weekday_df = df[df["date"].dt.dayofweek < 5]

    # Portfolio daily totals
    daily_totals = (
        weekday_df.groupby("date")
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    peak_footfall = int(daily_totals["footfall"].max())
    avg_footfall = int(daily_totals["footfall"].mean())
    total_capacity = _total_capacity(df)

    # Per-building utilisation stats
    bldg_daily = (
        weekday_df.groupby(["date", "building_id"])
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "first"))
        .reset_index()
    )
    bldg_daily["util"] = bldg_daily["footfall"] / bldg_daily["capacity"]
    bldg_stats = (
        bldg_daily.groupby("building_id")
        .agg(avg_util=("util", "mean"), peak_util=("util", "max"))
        .reset_index()
    )
    buildings_above_90 = int((bldg_stats["peak_util"] > 0.90).sum())
    buildings_below_60 = int((bldg_stats["avg_util"] < 0.60).sum())

    return {
        "peak_footfall": peak_footfall,
        "avg_footfall": avg_footfall,
        "buildings_above_90": buildings_above_90,
        "buildings_below_60": buildings_below_60,
        "total_capacity": total_capacity,
    }


# ---------------------------------------------------------------------------
# Day-of-week averages
# ---------------------------------------------------------------------------

def compute_dow_averages(daily_df: pd.DataFrame, horizon_days: int = 30) -> pd.DataFrame:
    df = get_horizon_df(daily_df, horizon_days).copy()
    if df.empty:
        return pd.DataFrame(columns=["day_of_week", "day_name", "avg_footfall", "avg_util_pct"])

    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_name"] = df["date"].dt.day_name()

    by_day = (
        df.groupby(["date", "day_of_week", "day_name"])
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    by_day["util_pct"] = by_day["footfall"] / by_day["capacity"] * 100

    dow_avg = (
        by_day.groupby(["day_of_week", "day_name"])
        .agg(avg_footfall=("footfall", "mean"), avg_util_pct=("util_pct", "mean"))
        .reset_index()
        .sort_values("day_of_week")
    )
    return dow_avg


# ---------------------------------------------------------------------------
# Monthly utilisation (for heatmap)
# ---------------------------------------------------------------------------

def compute_monthly_utilization(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Returns long-form DataFrame: building_id, building_name, month_label, util_pct."""
    df = daily_df[daily_df["date"].dt.dayofweek < 5].copy()
    df["year_month"] = df["date"].dt.to_period("M")

    # Aggregate to building-day level first so tower rows are correctly summed
    bldg_day = (
        df.groupby(["year_month", "date", "building_id", "building_name"])
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    monthly = (
        bldg_day.groupby(["year_month", "building_id", "building_name"])
        .agg(avg_footfall=("footfall", "mean"), capacity=("capacity", "first"))
        .reset_index()
    )
    monthly["util_pct"] = (monthly["avg_footfall"] / monthly["capacity"] * 100).clip(upper=120)
    monthly["month_label"] = monthly["year_month"].dt.strftime("%b %Y")
    monthly["month_order"] = monthly["year_month"].apply(lambda p: str(p))
    return monthly


# ---------------------------------------------------------------------------
# Long-term KPIs
# ---------------------------------------------------------------------------

def compute_long_term_kpis(daily_df: pd.DataFrame, horizon_months: int = 12) -> dict:
    today = pd.Timestamp(date.today())
    end = today + pd.Timedelta(days=horizon_months * 30)
    df = daily_df[(daily_df["date"] >= today) & (daily_df["date"] < end)]
    weekday_df = df[df["date"].dt.dayofweek < 5]

    if weekday_df.empty:
        return {"avg_monthly_footfall": 0, "avg_util_pct": 0.0, "surplus_seats": 0, "buildings_below_50": 0, "total_capacity": 0}

    total_cap = _total_capacity(df)

    daily_totals = (
        weekday_df.groupby("date")
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    avg_daily_footfall = daily_totals["footfall"].mean()
    avg_util_pct = round((daily_totals["footfall"] / daily_totals["capacity"]).mean() * 100, 1)
    surplus_seats = int(total_cap - avg_daily_footfall)

    bldg_util = (
        weekday_df.groupby("building_id")
        .apply(lambda g: (g["footfall"] / g["capacity"]).mean())
    )
    buildings_below_50 = int((bldg_util < 0.50).sum())

    # Avg monthly footfall = avg working-day footfall × 20 working days
    avg_monthly_footfall = int(avg_daily_footfall * 20)

    return {
        "avg_monthly_footfall": avg_monthly_footfall,
        "avg_util_pct": avg_util_pct,
        "surplus_seats": surplus_seats,
        "buildings_below_50": buildings_below_50,
        "total_capacity": total_cap,
    }


# ---------------------------------------------------------------------------
# City-level capacity metrics table
# ---------------------------------------------------------------------------

def compute_city_capacity_metrics(daily_df: pd.DataFrame, horizon_months: int = 12) -> pd.DataFrame:
    today = pd.Timestamp(date.today())
    end = today + pd.Timedelta(days=horizon_months * 30)
    df = daily_df[(daily_df["date"] >= today) & (daily_df["date"] < end)]
    weekday_df = df[df["date"].dt.dayofweek < 5]
    if weekday_df.empty:
        return pd.DataFrame(columns=["City", "Utilization %", "Surplus", "Deficit"])

    records = []
    for city, grp in weekday_df.groupby("city"):
        city_cap = _total_capacity(grp)
        daily_city = grp.groupby("date")["footfall"].sum()
        avg_daily = daily_city.mean()
        util_pct = round(avg_daily / city_cap * 100, 1)
        surplus = int(city_cap - avg_daily)
        deficit = max(0, -surplus)
        records.append({
            "City": city,
            "Utilization %": f"{util_pct}%",
            "Surplus": f"+{surplus}" if surplus >= 0 else str(surplus),
            "Deficit": f"-{deficit}" if deficit > 0 else "0",
        })

    return pd.DataFrame(records).sort_values("City")


# ---------------------------------------------------------------------------
# Insights generation
# ---------------------------------------------------------------------------

def generate_insights_short_term(daily_df: pd.DataFrame, horizon_days: int = 30) -> List[str]:
    df = get_horizon_df(daily_df, horizon_days)
    weekday_df = df[df["date"].dt.dayofweek < 5]
    if weekday_df.empty:
        return ["No forecast data available for this selection."]

    insights = []

    # Aggregate to building-day level first so tower rows are correctly summed
    bldg_day = (
        weekday_df.groupby(["date", "building_id", "building_name"])
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    bldg_day["util"] = bldg_day["footfall"] / bldg_day["capacity"]

    def _bldg_stats(g):
        peak_idx = g["util"].idxmax()
        return pd.Series({
            "avg_util": g["util"].mean(),
            "peak_util": g["util"].max(),
            "peak_date": g.loc[peak_idx, "date"].strftime("%b %d"),
        })

    bldg_stats = (
        bldg_day.groupby(["building_id", "building_name"])[["date", "util"]]
        .apply(_bldg_stats)
        .reset_index()
    )

    for _, row in bldg_stats[bldg_stats["avg_util"] >= 0.85].iterrows():
        insights.append(
            f"⚠️ **{row['building_name']}** projected at {row['avg_util']*100:.0f}% avg utilization "
            f"— peak on {row['peak_date']}"
        )

    dow_df = compute_dow_averages(daily_df, horizon_days)
    if not dow_df.empty:
        fri = dow_df[dow_df["day_name"] == "Friday"]["avg_util_pct"]
        wed = dow_df[dow_df["day_name"] == "Wednesday"]["avg_util_pct"]
        if len(fri) > 0 and len(wed) > 0:
            insights.append(
                f"📉 Friday footfall averages **{fri.values[0]:.0f}%** utilization vs "
                f"**{wed.values[0]:.0f}%** on Wednesday"
            )

    for _, row in bldg_stats[bldg_stats["avg_util"] < 0.60].iterrows():
        insights.append(
            f"📊 **{row['building_name']}** under-utilized at {row['avg_util']*100:.0f}% average occupancy"
        )

    if not insights:
        insights.append("✅ All buildings within normal utilization range for this window.")

    return insights[:5]


def generate_insights_long_term(daily_df: pd.DataFrame, horizon_months: int = 12) -> List[str]:
    today = pd.Timestamp(date.today())
    end = today + pd.Timedelta(days=horizon_months * 30)
    df = daily_df[(daily_df["date"] >= today) & (daily_df["date"] < end)]
    weekday_df = df[df["date"].dt.dayofweek < 5]
    if weekday_df.empty:
        return ["No long-term forecast available for this selection."]

    weekday_df = weekday_df.copy()
    weekday_df["year_month"] = weekday_df["date"].dt.to_period("M")

    insights = []

    # Aggregate to building-day level first so tower rows are correctly summed
    bldg_day_lt = (
        weekday_df.groupby(["date", "building_id", "building_name", "year_month"])
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    bldg_day_lt["util"] = bldg_day_lt["footfall"] / bldg_day_lt["capacity"]
    bldg_monthly = (
        bldg_day_lt.groupby(["building_id", "building_name", "year_month"])
        .agg(monthly_util=("util", "mean"))
        .reset_index()
    )

    breach = bldg_monthly[bldg_monthly["monthly_util"] >= 0.90]
    for bldg_id in breach["building_id"].unique():
        rows = breach[breach["building_id"] == bldg_id]
        first_month = str(rows["year_month"].min())
        bldg_name = rows["building_name"].iloc[0]
        insights.append(
            f"⚠️ **{bldg_name}** projected to exceed 90% avg utilization by **{first_month}**"
        )

    bldg_avg = bldg_monthly.groupby(["building_id", "building_name"])["monthly_util"].mean()
    for (_, bldg_name), avg_util in bldg_avg.items():
        if avg_util < 0.55:
            insights.append(
                f"📊 **{bldg_name}** projected at only {avg_util*100:.0f}% avg utilization "
                f"over {horizon_months} months — consider consolidation"
            )

    if not insights:
        insights.append("✅ Portfolio capacity appears balanced over the forecast horizon.")

    return insights[:5]


# ---------------------------------------------------------------------------
# Scenario adjustments
# ---------------------------------------------------------------------------

def apply_scenario_adjustments(
    daily_df: pd.DataFrame,
    date_range: Tuple,
    adjustments: Dict[str, bool],
    custom_factor_pct: float = 0.0,
    scope: str = "all",
    scope_values: Optional[List[str]] = None,
    # Deprecated: use scope + scope_values instead
    building_filter: Optional[List[str]] = None,
    lob_filter: Optional[List[str]] = None,
    # Override multipliers (e.g. from Admin config); falls back to SCENARIO_MULTIPLIERS
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    # Backward-compat: map old params to new scope model
    if building_filter and scope == "all":
        scope = "buildings"
        scope_values = building_filter
    elif lob_filter and scope == "all":
        scope = "lob"
        scope_values = lob_filter

    _mults = scenario_multipliers if scenario_multipliers is not None else SCENARIO_MULTIPLIERS

    df = daily_df.copy()
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1])

    combined_mult = 1.0
    for key, selected in adjustments.items():
        if selected and key in _mults:
            combined_mult *= _mults[key]
    if custom_factor_pct != 0.0:
        combined_mult *= 1.0 + custom_factor_pct / 100.0

    mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    if scope == "buildings" and scope_values:
        mask &= df["building_id"].isin(scope_values)
    elif scope == "lob" and scope_values:
        mask &= df["lob"].isin(scope_values)
    # scope == "all" or empty scope_values → no additional filter

    df.loc[mask, "footfall"] = (df.loc[mask, "footfall"] * combined_mult).round().astype(int).clip(lower=0)
    df["utilization_pct"] = (df["footfall"] / df["capacity"]).clip(upper=1.30)
    return df


def compute_live_insights(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
    scope: str = "all",
    scope_values: Optional[List[str]] = None,
    capacity_threshold: float = 0.90,
) -> List[str]:
    """Generate live quantified impact bullets for Mode A event adjustments."""
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1])

    base_win = baseline_df[(baseline_df["date"] >= start_ts) & (baseline_df["date"] <= end_ts)]
    scen_win = scenario_df[(scenario_df["date"] >= start_ts) & (scenario_df["date"] <= end_ts)]

    if base_win.empty:
        return ["ℹ️ No data in the selected event period."]

    base_total = int(base_win["footfall"].sum())
    scen_total = int(scen_win["footfall"].sum())
    delta = scen_total - base_total

    if delta == 0:
        return ["ℹ️ No adjustments active — select an event or set a custom factor to see impact."]

    insights = []

    # 1. Total footfall delta
    direction = "adds" if delta > 0 else "reduces"
    insights.append(
        f"📊 This scenario **{direction} {abs(delta):,} total footfall** over the event period"
    )

    # 2. Additional peak-risk days
    base_daily = base_win.groupby("date").agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
    scen_daily = scen_win.groupby("date").agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
    base_daily["util"] = base_daily["footfall"] / base_daily["capacity"]
    scen_daily["util"] = scen_daily["footfall"] / scen_daily["capacity"]
    base_risk_days = int((base_daily["util"] > capacity_threshold).sum())
    scen_risk_days = int((scen_daily["util"] > capacity_threshold).sum())
    risk_delta = scen_risk_days - base_risk_days
    pct_label = int(capacity_threshold * 100)
    if risk_delta > 0:
        insights.append(
            f"⚠️ **{risk_delta} additional peak-risk day{'s' if risk_delta != 1 else ''}** "
            f"(>{pct_label}% capacity) — up from {base_risk_days} baseline"
        )
    elif risk_delta < 0:
        insights.append(
            f"✅ **{abs(risk_delta)} fewer peak-risk day{'s' if abs(risk_delta) != 1 else ''}** "
            f"(>{pct_label}% capacity) — down from {base_risk_days} baseline"
        )
    else:
        insights.append(
            f"ℹ️ Peak-risk days unchanged at **{base_risk_days}** day{'s' if base_risk_days != 1 else ''} (>{pct_label}% capacity)"
        )

    # 3. Avg daily footfall change
    window_days = base_daily.shape[0]
    if window_days > 0:
        avg_delta = delta / window_days
        insights.append(
            f"📅 Avg daily footfall change: **{avg_delta:+,.0f} seats/day** over {window_days} event day{'s' if window_days != 1 else ''}"
        )

    # 4. Top impacted building
    per_bldg_base = base_win.groupby(["building_id", "building_name"])["footfall"].sum()
    per_bldg_scen = scen_win.groupby(["building_id", "building_name"])["footfall"].sum()
    diff = per_bldg_scen - per_bldg_base
    if not diff.empty and diff.abs().max() > 0:
        top_idx = diff.abs().idxmax()
        top_diff = diff[top_idx]
        top_base = per_bldg_base.get(top_idx, 0)
        top_name = top_idx[1] if isinstance(top_idx, tuple) else str(top_idx)
        if top_base > 0:
            top_pct = top_diff / top_base * 100
            insights.append(
                f"🏢 Top impacted building: **{top_name}** ({top_pct:+.0f}%, {top_diff:+,.0f} seats)"
            )

    # 5. Scope coverage (only when narrowed)
    total_buildings = baseline_df["building_id"].nunique()
    if scope == "buildings" and scope_values:
        scoped_n = len([v for v in scope_values if v in baseline_df["building_id"].unique()])
        insights.append(
            f"🎯 Adjustment applies to **{scoped_n} of {total_buildings} building{'s' if total_buildings != 1 else ''}**"
        )
    elif scope == "lob" and scope_values:
        scoped_bldgs = baseline_df[baseline_df["lob"].isin(scope_values)]["building_id"].nunique()
        lob_str = ", ".join(scope_values[:3]) + ("…" if len(scope_values) > 3 else "")
        insights.append(
            f"🎯 Adjustment applies to **{scoped_bldgs} of {total_buildings} building{'s' if total_buildings != 1 else ''}** (LoB: {lob_str})"
        )

    return insights


def compute_scenario_kpis(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
) -> dict:
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1])

    def _totals(df, weekdays_only=False):
        sliced = df[(df["date"] >= start_ts) & (df["date"] <= end_ts)]
        if weekdays_only:
            sliced = sliced[sliced["date"].dt.dayofweek < 5]
        return sliced.groupby("date")["footfall"].sum()

    base_all = _totals(baseline_df, weekdays_only=False)
    base_wday = _totals(baseline_df, weekdays_only=True)
    scen_wday = _totals(scenario_df, weekdays_only=True)

    baseline_total = int(base_all.sum())
    scenario_total = int(_totals(scenario_df, weekdays_only=False).sum())
    window_weekdays = int(base_wday.shape[0])
    window_days = int(base_all.shape[0])

    return {
        "baseline_footfall": baseline_total,
        "scenario_footfall": scenario_total,
        "delta": scenario_total - baseline_total,
        "baseline_avg_daily": round(base_wday.sum() / window_weekdays) if window_weekdays else 0,
        "scenario_avg_daily": round(scen_wday.sum() / window_weekdays) if window_weekdays else 0,
        "window_days": window_days,
        "window_weekdays": window_weekdays,
    }


def compute_building_impact_table(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
) -> pd.DataFrame:
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1])

    def agg(df):
        return (
            df[(df["date"] >= start_ts) & (df["date"] <= end_ts)]
            .groupby(["building_id", "building_name"])
            .agg(total=("footfall", "sum"))
            .reset_index()
        )

    base_agg = agg(baseline_df).rename(columns={"total": "Baseline Forecast"})
    scen_agg = agg(scenario_df).rename(columns={"total": "Scenario Forecast"})
    merged = base_agg.merge(scen_agg, on=["building_id", "building_name"])
    merged["Difference"] = merged["Scenario Forecast"] - merged["Baseline Forecast"]
    return merged.rename(columns={"building_name": "Building"})[
        ["Building", "Baseline Forecast", "Scenario Forecast", "Difference"]
    ]


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def plot_daily_forecast(daily_df: pd.DataFrame, horizon_days: int = 30) -> go.Figure:
    """Line chart: daily total footfall vs total capacity over the horizon."""
    df = get_horizon_df(daily_df, horizon_days)
    if df.empty:
        return go.Figure()

    daily = (
        df.groupby("date")
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["footfall"],
        mode="lines", name="Forecasted Footfall",
        line=dict(color="#1a3c5e", width=2),
        fill="tozeroy", fillcolor="rgba(26,60,94,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["capacity"],
        mode="lines", name="Capacity Limit",
        line=dict(color="#dc3545", width=2, dash="dot"),
    ))
    fig.update_layout(
        title=f"Daily Forecasted Footfall vs Capacity — Next {horizon_days} Days",
        xaxis_title="Date",
        yaxis_title="Seats",
        legend=dict(orientation="h", y=-0.2),
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig


def plot_dow_bar(dow_df: pd.DataFrame) -> go.Figure:
    """Bar chart: average footfall by day of week."""
    if dow_df.empty:
        return go.Figure()

    colors = [
        "#dc3545" if u > 90 else "#ffc107" if u > 75 else "#1a3c5e"
        for u in dow_df["avg_util_pct"]
    ]

    fig = go.Figure(go.Bar(
        x=dow_df["day_name"],
        y=dow_df["avg_util_pct"].round(1),
        marker_color=colors,
        text=dow_df["avg_util_pct"].round(0).astype(int).astype(str) + "%",
        textposition="outside",
    ))
    fig.add_hline(y=90, line_dash="dot", line_color="#dc3545",
                  annotation_text="90% threshold", annotation_position="right")
    fig.update_layout(
        title="Avg Footfall by Day of Week (% Utilization)",
        xaxis_title="", yaxis_title="Avg Utilization %",
        yaxis=dict(range=[0, 115]),
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def plot_capacity_calendar(daily_df: pd.DataFrame, horizon_days: int = 30) -> go.Figure:
    """Calendar grid where cells are coloured by utilization level."""
    df = get_horizon_df(daily_df, horizon_days)
    if df.empty:
        return go.Figure()

    daily = (
        df.groupby("date")
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    daily["util_pct"] = daily["footfall"] / daily["capacity"] * 100
    daily["day"] = daily["date"].dt.day
    daily["dow"] = daily["date"].dt.dayofweek          # 0=Mon
    daily["month_str"] = daily["date"].dt.strftime("%b %Y")
    daily["week"] = daily["date"].apply(
        lambda d: (d - daily["date"].min()).days // 7
    )

    # Discrete color
    def cell_color(u):
        if u > 90:
            return "#f8d7da"
        elif u > 75:
            return "#fff3cd"
        elif u > 5:
            return "#d4edda"
        return "#e9ecef"

    def text_color(u):
        return "#721c24" if u > 90 else "#856404" if u > 75 else "#155724" if u > 5 else "#adb5bd"

    dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    fig = go.Figure()

    for _, row in daily.iterrows():
        week = row["week"]
        dow = row["dow"]
        util = row["util_pct"]
        label = f"{row['date'].strftime('%b %d')}<br>{util:.0f}%"
        if util > 90:
            label += "<br><b>Over capacity</b>"
        elif util < 60 and util > 5:
            label += "<br>Under capacity"

        fig.add_shape(
            type="rect",
            x0=dow - 0.45, x1=dow + 0.45,
            y0=week - 0.45, y1=week + 0.45,
            fillcolor=cell_color(util),
            line=dict(color="white", width=2),
        )
        fig.add_annotation(
            x=dow, y=week,
            text=label,
            showarrow=False,
            font=dict(size=9, color=text_color(util)),
        )

    n_weeks = int(daily["week"].max()) + 1
    fig.update_layout(
        title=f"Capacity Calendar — Next {horizon_days} Days",
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(7)),
            ticktext=dow_labels,
            range=[-0.6, 6.6],
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(n_weeks)),
            ticktext=[f"Wk {i+1}" for i in range(n_weeks)],
            range=[-0.6, n_weeks - 0.4],
            autorange="reversed",
        ),
        height=max(250, n_weeks * 80),
        margin=dict(l=50, r=10, t=40, b=10),
    )
    return fig


def plot_building_heatmap(monthly_df: pd.DataFrame) -> go.Figure:
    """Building × Month utilization heatmap."""
    if monthly_df.empty:
        return go.Figure()

    # Pivot: buildings as rows, months as columns
    pivot = monthly_df.pivot_table(
        index="building_name",
        columns="month_label",
        values="util_pct",
        aggfunc="mean",
    )
    # Sort columns chronologically using month_order
    month_order = (
        monthly_df[["month_label", "month_order"]]
        .drop_duplicates()
        .sort_values("month_order")["month_label"]
        .tolist()
    )
    cols_present = [c for c in month_order if c in pivot.columns]
    pivot = pivot[cols_present]

    fig = px.imshow(
        pivot,
        color_continuous_scale=[[0, "#f0f4f8"], [0.5, "#4a7dba"], [0.85, "#1a3c5e"], [1.0, "#dc3545"]],
        zmin=0, zmax=100,
        aspect="auto",
        text_auto=".0f",
        labels=dict(color="Util %"),
    )
    fig.update_layout(
        title="Monthly Utilization by Building (%)",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        coloraxis_colorbar=dict(title="Util %"),
    )
    fig.update_traces(textfont_size=10)
    return fig


def plot_monthly_forecast_simple(daily_df: pd.DataFrame) -> go.Figure:
    """Simpler monthly forecast using direct groupby (avoids nested lambda)."""
    df = daily_df[daily_df["date"].dt.dayofweek < 5].copy()
    if df.empty:
        return go.Figure()

    df["year_month"] = df["date"].dt.to_period("M")
    # First aggregate by date to get daily totals, then average by month
    daily_totals = df.groupby(["date", "year_month"]).agg(
        footfall=("footfall", "sum"),
        capacity=("capacity", "sum"),
    ).reset_index()
    monthly = daily_totals.groupby("year_month").agg(
        avg_footfall=("footfall", "mean"),
        avg_capacity=("capacity", "mean"),
    ).reset_index()
    monthly["month_label"] = monthly["year_month"].dt.strftime("%b %Y")
    monthly = monthly.sort_values("year_month")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month_label"], y=monthly["avg_footfall"].round(),
        mode="lines+markers", name="Avg Daily Footfall",
        line=dict(color="#1a3c5e", width=2.5),
        fill="tozeroy", fillcolor="rgba(26,60,94,0.08)",
        marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=monthly["month_label"], y=monthly["avg_capacity"],
        mode="lines", name="Capacity",
        line=dict(color="#dc3545", width=2, dash="dot"),
    ))
    fig.update_layout(
        title="Monthly Avg Daily Footfall vs Capacity",
        xaxis_title="", yaxis_title="Avg Daily Seats",
        legend=dict(orientation="h", y=-0.25),
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig


def plot_scenario_wedge(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
    horizon_days: int = 60,
) -> go.Figure:
    """Baseline vs scenario split-line chart with shaded wedge."""
    today = pd.Timestamp(date.today())
    end = today + pd.Timedelta(days=horizon_days)
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1])

    def daily_totals(df):
        return (
            df[(df["date"] >= today) & (df["date"] < end)]
            .groupby("date")
            .agg(footfall=("footfall", "sum"))
            .reset_index()
        )

    base = daily_totals(baseline_df)
    scen = daily_totals(scenario_df)
    merged = base.merge(scen, on="date", suffixes=("_base", "_scen"))

    fig = go.Figure()

    # Shaded wedge area
    fig.add_trace(go.Scatter(
        x=pd.concat([merged["date"], merged["date"][::-1]]),
        y=pd.concat([merged["footfall_scen"], merged["footfall_base"][::-1]]),
        fill="toself",
        fillcolor="rgba(26,60,94,0.10)",
        line=dict(color="rgba(255,255,255,0)"),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Baseline line
    fig.add_trace(go.Scatter(
        x=merged["date"], y=merged["footfall_base"],
        mode="lines", name="Baseline Footfall",
        line=dict(color="#6c757d", width=2.5),
    ))

    # Scenario line
    fig.add_trace(go.Scatter(
        x=merged["date"], y=merged["footfall_scen"],
        mode="lines", name="Scenario Footfall",
        line=dict(color="#1a3c5e", width=2.5, dash="dash"),
    ))

    # Vertical markers for scenario window
    for dt in [start_ts, end_ts]:
        if today <= dt < end:
            fig.add_vline(x=dt, line_dash="dot", line_color="#ffc107", line_width=1.5)

    fig.update_layout(
        title="Scenario Impact — Baseline vs Adjusted Footfall",
        xaxis_title="Date", yaxis_title="Total Seats",
        legend=dict(orientation="h", y=-0.2),
        height=340,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig


# ---------------------------------------------------------------------------
# Policy Simulation (RTO mandate / seat allocation target)
# ---------------------------------------------------------------------------

BASELINE_RTO_DAYS: float = 3.5  # weighted avg baked into sample data


def simulate_rto_policy(
    daily_df: pd.DataFrame,
    new_rto_days: float,
    baseline_rto_days: float = BASELINE_RTO_DAYS,
) -> pd.DataFrame:
    """Return a copy of daily_df with footfall scaled by new_rto / baseline_rto.

    Increasing RTO mandate → footfall goes up proportionally.
    Decreasing → footfall goes down.
    """
    if baseline_rto_days <= 0:
        return daily_df.copy()
    scale = new_rto_days / baseline_rto_days
    df = daily_df.copy()
    df["footfall"] = (df["footfall"] * scale).round().astype(int).clip(lower=0)
    df["utilization_pct"] = (df["footfall"] / df["capacity"]).clip(upper=1.30)
    return df


def compute_seat_gap_by_building(
    daily_df: pd.DataFrame,
    target_utilization: float = 0.80,
    horizon_days: int = 30,
) -> pd.DataFrame:
    """Per building: seats_needed = peak_footfall / target_utilization; gap = capacity - seats_needed.

    Returns: Building | Current Capacity | Seats Needed | Surplus / Deficit
    """
    df = get_horizon_df(daily_df, horizon_days)
    weekday_df = df[df["date"].dt.dayofweek < 5]
    if weekday_df.empty:
        return pd.DataFrame(
            columns=["Building", "Current Capacity", "Seats Needed", "Surplus / Deficit"]
        )

    target_util = max(0.01, target_utilization)

    # Aggregate to building-day level first so tower rows are correctly summed
    bldg_day = (
        weekday_df.groupby(["date", "building_id", "building_name"])
        .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    bldg = (
        bldg_day.groupby(["building_id", "building_name"])
        .agg(
            peak_footfall=("footfall", "max"),
            avg_footfall=("footfall", "mean"),
            capacity=("capacity", "first"),
        )
        .reset_index()
    )
    bldg["Seats Needed"] = (bldg["peak_footfall"] / target_util).round().astype(int)
    bldg["Surplus / Deficit"] = bldg["capacity"] - bldg["Seats Needed"]
    return bldg.rename(columns={"building_name": "Building", "capacity": "Current Capacity"})[
        ["Building", "Current Capacity", "Seats Needed", "Surplus / Deficit"]
    ]


def compute_policy_kpis(
    baseline_df: pd.DataFrame,
    policy_df: pd.DataFrame,
    target_utilization: float = 0.80,
    horizon_days: int = 30,
) -> dict:
    """Compare baseline vs policy scenario: demand change + portfolio seat gap."""
    def avg_daily(df):
        wdf = get_horizon_df(df, horizon_days)
        wdf = wdf[wdf["date"].dt.dayofweek < 5]
        if wdf.empty:
            return 0.0
        return wdf.groupby("date")["footfall"].sum().mean()

    base_demand = avg_daily(baseline_df)
    policy_demand = avg_daily(policy_df)

    # Portfolio seat gap under new policy
    gap_df = compute_seat_gap_by_building(policy_df, target_utilization, horizon_days)
    if gap_df.empty:
        portfolio_gap = 0
    else:
        portfolio_gap = int(gap_df["Surplus / Deficit"].sum())

    total_cap = _total_capacity(get_horizon_df(policy_df, horizon_days))

    return {
        "base_demand": int(base_demand),
        "policy_demand": int(policy_demand),
        "demand_delta": int(policy_demand - base_demand),
        "portfolio_gap": portfolio_gap,
        "total_capacity": total_cap,
    }


def plot_rto_comparison(
    baseline_df: pd.DataFrame,
    policy_df: pd.DataFrame,
) -> go.Figure:
    """Two monthly footfall lines: current policy (gray solid) vs new RTO policy (blue dashed)."""

    def monthly_series(df):
        wdf = df[df["date"].dt.dayofweek < 5].copy()
        wdf["year_month"] = wdf["date"].dt.to_period("M")
        daily = (
            wdf.groupby(["date", "year_month"])
            .agg(footfall=("footfall", "sum"))
            .reset_index()
        )
        return (
            daily.groupby("year_month")
            .agg(avg_footfall=("footfall", "mean"))
            .reset_index()
            .sort_values("year_month")
            .assign(month_label=lambda d: d["year_month"].dt.strftime("%b %Y"))
        )

    base_m = monthly_series(baseline_df)
    policy_m = monthly_series(policy_df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=base_m["month_label"], y=base_m["avg_footfall"].round(),
        mode="lines+markers", name="Current Policy",
        line=dict(color="#6c757d", width=2.5),
        marker=dict(size=5),
    ))
    fig.add_trace(go.Scatter(
        x=policy_m["month_label"], y=policy_m["avg_footfall"].round(),
        mode="lines+markers", name="New RTO Policy",
        line=dict(color="#1a3c5e", width=2.5, dash="dash"),
        marker=dict(size=5),
    ))
    fig.update_layout(
        title="Monthly Avg Daily Footfall — Current vs New RTO Policy",
        xaxis_title="", yaxis_title="Avg Daily Seats",
        legend=dict(orientation="h", y=-0.2),
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig
