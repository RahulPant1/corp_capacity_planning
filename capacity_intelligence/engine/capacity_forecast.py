"""Capacity Intelligence forecasting engine — 4-dataset model.

Column conventions (matching ci_sample_data.py):
  Date, Day, City, Building Name, Floor, LOB, Leader
  Holiday Flag, Optional Holiday Flag, Optional Holiday Name, US Holiday Flag
  Employee Count Predicted  ← the footfall signal
  Total Capacity            ← from DS1 (per floor; SHARED across LOBs on same floor)
  Allocated Seats           ← from DS2 (per LOB per floor)
  Headcount                 ← from DS3 (per LOB, portfolio-wide)
  Utilization Pct           ← Predicted / Capacity (clipped at 1.30)
  Seat Gap                  ← Allocated Seats - Predicted
  HC Gap                    ← Allocated Seats - Headcount

Capacity aggregation rule:
  Total Capacity is the same for all LOBs on the same floor.
  Always de-duplicate on (City, Building Name, Floor) before summing capacity
  to avoid counting a floor's capacity once per LOB.
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Column name constants
# ---------------------------------------------------------------------------
C_DATE      = "Date"
C_CITY      = "City"
C_BUILDING  = "Building Name"
C_FLOOR     = "Floor"
C_LOB       = "LOB"
C_LEADER    = "Leader"
C_PREDICTED = "Employee Count Predicted"
C_CAPACITY  = "Total Capacity"
C_ALLOC     = "Allocated Seats"
C_HEADCOUNT = "Headcount"
C_UTIL      = "Utilization Pct"
C_SEAT_GAP  = "Seat Gap"
C_HOL       = "Holiday Flag"
C_OPT_HOL   = "Optional Holiday Flag"
C_US_HOL    = "US Holiday Flag"

FLOOR_KEY    = [C_CITY, C_BUILDING, C_FLOOR]
BUILDING_KEY = [C_CITY, C_BUILDING]

# ---------------------------------------------------------------------------
# Scenario event multipliers
# ---------------------------------------------------------------------------
SCENARIO_MULTIPLIERS: Dict[str, float] = {
    "townhall":           1.20,
    "leadership_visit":   1.15,
    "weather_alert":      0.70,
    "traffic_disruption": 0.80,
    "mandatory_holiday":  0.10,
    "optional_holiday":   0.60,
    "us_holiday":         0.75,
}

# Baseline RTO days/week baked into sample data (used only for display context)
BASELINE_RTO_DAYS: float = 3.5

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dedup_capacity(df: pd.DataFrame) -> int:
    """Sum Total Capacity across unique (City, Building Name, Floor) rows.

    Multiple LOBs share the same floor — de-duplicating prevents double-counting.
    """
    return int(df.drop_duplicates(subset=FLOOR_KEY)[C_CAPACITY].sum())


def _building_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily_df to (Date, City, Building Name) with correct capacity.

    Returns: Date, City, Building Name, predicted_sum, capacity
    capacity is summed across unique floors (not across LOBs).
    """
    # Predicted: sum all LOBs on all floors per building per day
    pred = (
        df.groupby([C_DATE, C_CITY, C_BUILDING])[C_PREDICTED]
        .sum()
        .reset_index()
        .rename(columns={C_PREDICTED: "predicted_sum"})
    )
    # Capacity: de-dup across LOBs before aggregating to building level
    cap = (
        df.drop_duplicates(subset=[C_DATE, *FLOOR_KEY])
        .groupby([C_DATE, C_CITY, C_BUILDING])[C_CAPACITY]
        .sum()
        .reset_index()
        .rename(columns={C_CAPACITY: "capacity"})
    )
    merged = pred.merge(cap, on=[C_DATE, C_CITY, C_BUILDING], how="left")
    merged["util"] = merged["predicted_sum"] / merged["capacity"]
    return merged


# ---------------------------------------------------------------------------
# Filtering and slicing
# ---------------------------------------------------------------------------

def filter_df(
    daily_df: pd.DataFrame,
    buildings: Optional[List[str]] = None,
    cities: Optional[List[str]] = None,
    lobs: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Filter working DataFrame by building name(s), city, and/or LOB."""
    df = daily_df
    if buildings:
        df = df[df[C_BUILDING].isin(buildings)]
    if cities:
        df = df[df[C_CITY].isin(cities)]
    if lobs:
        df = df[df[C_LOB].isin(lobs)]
    return df


def get_data_anchor(daily_df: pd.DataFrame) -> date:
    """Effective start date for horizon filtering.

    Returns today if today falls within the loaded data's date range.
    Falls back to the data's first date when today is outside the range
    (e.g. the loaded file covers a past period or a future-dated export).
    This ensures all views show data from the loaded dataset regardless of
    when the app is being run.
    """
    data_min = daily_df[C_DATE].min().date()
    data_max = daily_df[C_DATE].max().date()
    today = date.today()
    if data_min <= today <= data_max:
        return today
    return data_min


def get_horizon_df(daily_df: pd.DataFrame, horizon_days: int = 30) -> pd.DataFrame:
    anchor = pd.Timestamp(get_data_anchor(daily_df))
    end = anchor + pd.Timedelta(days=horizon_days)
    return daily_df[(daily_df[C_DATE] >= anchor) & (daily_df[C_DATE] < end)]


def get_weekday_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[df[C_DATE].dt.dayofweek < 5]


# ---------------------------------------------------------------------------
# Portfolio-level KPIs (short-term)
# ---------------------------------------------------------------------------

def compute_portfolio_kpis(
    daily_df: pd.DataFrame,
    horizon_days: int = 30,
) -> dict:
    """Peak predicted, avg predicted, floors >90%, floors <60%, total capacity."""
    df = get_horizon_df(daily_df, horizon_days)
    weekday_df = get_weekday_df(df)
    if weekday_df.empty:
        return {
            "peak_footfall": 0, "avg_footfall": 0,
            "buildings_above_90": 0, "buildings_below_60": 0,
            "total_capacity": 0,
        }

    total_capacity = _dedup_capacity(df)

    # Portfolio daily totals — sum predicted across all floors+LOBs
    daily_totals = weekday_df.groupby(C_DATE)[C_PREDICTED].sum()
    peak_footfall = int(daily_totals.max())
    avg_footfall  = int(daily_totals.mean())

    # Per-building utilisation (correct capacity)
    bldg_daily = _building_daily(weekday_df)
    bldg_stats = (
        bldg_daily.groupby(BUILDING_KEY)
        .agg(avg_util=("util", "mean"), peak_util=("util", "max"))
        .reset_index()
    )
    buildings_above_90 = int((bldg_stats["peak_util"] > 0.90).sum())
    buildings_below_60 = int((bldg_stats["avg_util"] < 0.60).sum())

    return {
        "peak_footfall":     peak_footfall,
        "avg_footfall":      avg_footfall,
        "buildings_above_90": buildings_above_90,
        "buildings_below_60": buildings_below_60,
        "total_capacity":    total_capacity,
    }


# ---------------------------------------------------------------------------
# Floor-level KPIs
# ---------------------------------------------------------------------------

def compute_floor_utilization(
    daily_df: pd.DataFrame,
    horizon_days: int = 30,
) -> pd.DataFrame:
    """Per-floor utilization table over the horizon window.

    Returns: City, Building Name, Floor, Avg Util %, Peak Util %, Risk
    """
    df = get_weekday_df(get_horizon_df(daily_df, horizon_days))
    if df.empty:
        return pd.DataFrame()

    # Sum predictions across LOBs per floor per day, then stats over time
    floor_day = (
        df.groupby([C_DATE, *FLOOR_KEY])
        .agg(predicted_sum=(C_PREDICTED, "sum"), capacity=(C_CAPACITY, "first"))
        .reset_index()
    )
    floor_day["util"] = floor_day["predicted_sum"] / floor_day["capacity"]

    floor_stats = (
        floor_day.groupby(FLOOR_KEY)
        .agg(
            avg_util=("util", "mean"),
            peak_util=("util", "max"),
            capacity=("capacity", "first"),
        )
        .reset_index()
    )
    floor_stats["Avg Util %"]  = (floor_stats["avg_util"]  * 100).round(1)
    floor_stats["Peak Util %"] = (floor_stats["peak_util"] * 100).round(1)
    floor_stats["Risk"] = floor_stats["peak_util"].apply(
        lambda u: "🔴 Over Capacity" if u > 0.90
        else ("🟡 Watch" if u > 0.75 else ("🔵 Under-utilized" if u < 0.60 else "🟢 Healthy"))
    )
    return floor_stats[[*FLOOR_KEY, "Avg Util %", "Peak Util %", "Risk", "capacity"]]


# ---------------------------------------------------------------------------
# LOB seat gap table (static: allocation vs headcount)
# ---------------------------------------------------------------------------

def compute_lob_gap_table(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Static LOB-level gap: Allocated Seats vs Headcount.

    Returns one row per LOB (summed across all floors/buildings).
    Seat Gap = Allocated Seats - Headcount  (negative = deficit)
    """
    if C_ALLOC not in daily_df.columns or C_HEADCOUNT not in daily_df.columns:
        return pd.DataFrame()

    # Allocation per LOB — de-dup to one row per (LOB, building, floor)
    alloc = (
        daily_df.drop_duplicates(subset=[C_LOB, *FLOOR_KEY])
        .groupby(C_LOB)[C_ALLOC]
        .sum()
        .reset_index()
        .rename(columns={C_ALLOC: "Total Allocated"})
    )
    hc = (
        daily_df.drop_duplicates(subset=C_LOB)
        [[C_LOB, C_HEADCOUNT]]
        .rename(columns={C_HEADCOUNT: "Headcount"})
    )
    df = alloc.merge(hc, on=C_LOB, how="left")
    df["Seat Gap"] = df["Total Allocated"] - df["Headcount"]
    df["Status"] = df["Seat Gap"].apply(
        lambda x: "✅ Surplus" if x >= 0 else "🔴 Deficit"
    )
    return df.sort_values("Seat Gap")


# ---------------------------------------------------------------------------
# Day-of-week averages
# ---------------------------------------------------------------------------

def compute_dow_averages(daily_df: pd.DataFrame, horizon_days: int = 30) -> pd.DataFrame:
    df = get_weekday_df(get_horizon_df(daily_df, horizon_days)).copy()
    if df.empty:
        return pd.DataFrame(columns=["day_of_week", "day_name", "avg_footfall", "avg_util_pct"])

    df["day_of_week"] = df[C_DATE].dt.dayofweek
    df["day_name"]    = df[C_DATE].dt.day_name()

    # Portfolio daily totals with correct capacity
    bldg_day = _building_daily(df)
    bldg_day["day_of_week"] = bldg_day[C_DATE].dt.dayofweek
    bldg_day["day_name"]    = bldg_day[C_DATE].dt.day_name()

    portfolio_day = (
        bldg_day.groupby([C_DATE, "day_of_week", "day_name"])
        .agg(predicted=("predicted_sum", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    portfolio_day["util_pct"] = portfolio_day["predicted"] / portfolio_day["capacity"] * 100

    dow_avg = (
        portfolio_day.groupby(["day_of_week", "day_name"])
        .agg(avg_footfall=("predicted", "mean"), avg_util_pct=("util_pct", "mean"))
        .reset_index()
        .sort_values("day_of_week")
    )
    return dow_avg


# ---------------------------------------------------------------------------
# Monthly utilisation (for heatmap)
# ---------------------------------------------------------------------------

def compute_monthly_utilization(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Building × Month utilization — used by heatmap chart."""
    df = get_weekday_df(daily_df).copy()
    df["year_month"] = df[C_DATE].dt.to_period("M")

    bldg_day = _building_daily(df)
    bldg_day["year_month"] = bldg_day[C_DATE].dt.to_period("M")

    monthly = (
        bldg_day.groupby([C_CITY, C_BUILDING, "year_month"])
        .agg(avg_predicted=("predicted_sum", "mean"), capacity=("capacity", "first"))
        .reset_index()
    )
    monthly["util_pct"]    = (monthly["avg_predicted"] / monthly["capacity"] * 100).clip(upper=120)
    monthly["month_label"] = monthly["year_month"].dt.strftime("%b %Y")
    monthly["month_order"] = monthly["year_month"].apply(str)
    monthly["building_name"] = monthly[C_BUILDING]  # alias for chart compat
    return monthly


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def generate_insights_short_term(daily_df: pd.DataFrame, horizon_days: int = 30) -> List[str]:
    df = get_weekday_df(get_horizon_df(daily_df, horizon_days))
    if df.empty:
        return ["No forecast data available for this selection."]

    bldg_day = _building_daily(df)

    def _bldg_stats(g):
        peak_idx  = g["util"].idxmax()
        return pd.Series({
            "avg_util":  g["util"].mean(),
            "peak_util": g["util"].max(),
            "peak_date": g.loc[peak_idx, C_DATE].strftime("%b %d"),
        })

    bldg_stats = (
        bldg_day.groupby(BUILDING_KEY)[["util", C_DATE]]
        .apply(_bldg_stats)
        .reset_index()
    )

    insights = []

    for _, row in bldg_stats[bldg_stats["avg_util"] >= 0.85].iterrows():
        insights.append(
            f"⚠️ **{row[C_BUILDING]}** projected at {row['avg_util']*100:.0f}% avg utilization "
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
            f"📊 **{row[C_BUILDING]}** under-utilized at {row['avg_util']*100:.0f}% average occupancy"
        )

    if not insights:
        insights.append("✅ All buildings within normal utilization range for this window.")

    return insights[:5]


# ---------------------------------------------------------------------------
# Scenario adjustments (Mode A — Event Impact)
# ---------------------------------------------------------------------------

def apply_scenario_adjustments(
    daily_df: pd.DataFrame,
    date_range: Tuple,
    adjustments: Dict[str, bool],
    custom_factor_pct: float = 0.0,
    scope: str = "all",
    scope_values: Optional[List[str]] = None,
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    _mults = scenario_multipliers if scenario_multipliers is not None else SCENARIO_MULTIPLIERS

    df = daily_df.copy()
    start_ts = pd.Timestamp(date_range[0])
    end_ts   = pd.Timestamp(date_range[1])

    combined_mult = 1.0
    for key, selected in adjustments.items():
        if selected and key in _mults:
            combined_mult *= _mults[key]
    if custom_factor_pct != 0.0:
        combined_mult *= 1.0 + custom_factor_pct / 100.0

    mask = (df[C_DATE] >= start_ts) & (df[C_DATE] <= end_ts)
    if scope == "buildings" and scope_values:
        mask &= df[C_BUILDING].isin(scope_values)
    elif scope == "lob" and scope_values:
        mask &= df[C_LOB].isin(scope_values)

    df.loc[mask, C_PREDICTED] = (
        df.loc[mask, C_PREDICTED] * combined_mult
    ).round().astype(int).clip(lower=0)

    df[C_UTIL] = (df[C_PREDICTED] / df[C_CAPACITY]).clip(upper=1.30).round(3)
    if C_SEAT_GAP in df.columns:
        df[C_SEAT_GAP] = df[C_ALLOC] - df[C_PREDICTED]
    return df


def compute_live_insights(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
    scope: str = "all",
    scope_values: Optional[List[str]] = None,
    capacity_threshold: float = 0.90,
) -> List[str]:
    start_ts = pd.Timestamp(date_range[0])
    end_ts   = pd.Timestamp(date_range[1])

    base_win = baseline_df[(baseline_df[C_DATE] >= start_ts) & (baseline_df[C_DATE] <= end_ts)]
    scen_win = scenario_df[(scenario_df[C_DATE] >= start_ts) & (scenario_df[C_DATE] <= end_ts)]

    if base_win.empty:
        return ["ℹ️ No data in the selected event period."]

    base_total = int(base_win[C_PREDICTED].sum())
    scen_total = int(scen_win[C_PREDICTED].sum())
    delta = scen_total - base_total

    if delta == 0:
        return ["ℹ️ No adjustments active — select an event or set a custom factor to see impact."]

    insights = []

    direction = "adds" if delta > 0 else "reduces"
    insights.append(
        f"📊 This scenario **{direction} {abs(delta):,} total predicted attendance** over the event period"
    )

    # Peak-risk days (building level, correct capacity)
    base_bldg = _building_daily(base_win)
    scen_bldg = _building_daily(scen_win)
    base_daily_port = base_bldg.groupby(C_DATE).apply(
        lambda g: g["predicted_sum"].sum() / g["capacity"].sum()
    )
    scen_daily_port = scen_bldg.groupby(C_DATE).apply(
        lambda g: g["predicted_sum"].sum() / g["capacity"].sum()
    )
    base_risk = int((base_daily_port > capacity_threshold).sum())
    scen_risk = int((scen_daily_port > capacity_threshold).sum())
    risk_delta = scen_risk - base_risk
    pct_label = int(capacity_threshold * 100)

    if risk_delta > 0:
        insights.append(
            f"⚠️ **{risk_delta} additional peak-risk day{'s' if risk_delta != 1 else ''}** "
            f"(>{pct_label}% capacity) — up from {base_risk} baseline"
        )
    elif risk_delta < 0:
        insights.append(
            f"✅ **{abs(risk_delta)} fewer peak-risk day{'s' if abs(risk_delta) != 1 else ''}** "
            f"(>{pct_label}% capacity) — down from {base_risk} baseline"
        )
    else:
        insights.append(
            f"ℹ️ Peak-risk days unchanged at **{base_risk}** (>{pct_label}% capacity)"
        )

    window_days = base_bldg[C_DATE].nunique()
    if window_days > 0:
        avg_delta = delta / window_days
        insights.append(
            f"📅 Avg daily footfall change: **{avg_delta:+,.0f} seats/day** over {window_days} event day{'s' if window_days != 1 else ''}"
        )

    # Top impacted building
    per_bldg_base = base_win.groupby(C_BUILDING)[C_PREDICTED].sum()
    per_bldg_scen = scen_win.groupby(C_BUILDING)[C_PREDICTED].sum()
    diff = per_bldg_scen - per_bldg_base
    if not diff.empty and diff.abs().max() > 0:
        top_bldg = diff.abs().idxmax()
        top_diff = int(diff[top_bldg])
        top_base = int(per_bldg_base.get(top_bldg, 0))
        if top_base > 0:
            top_pct = top_diff / top_base * 100
            insights.append(
                f"🏢 Top impacted building: **{top_bldg}** ({top_pct:+.0f}%, {top_diff:+,.0f} seats)"
            )

    total_buildings = baseline_df[C_BUILDING].nunique()
    if scope == "buildings" and scope_values:
        scoped_n = len([v for v in scope_values if v in baseline_df[C_BUILDING].unique()])
        insights.append(
            f"🎯 Adjustment applies to **{scoped_n} of {total_buildings} building{'s' if total_buildings != 1 else ''}**"
        )
    elif scope == "lob" and scope_values:
        scoped_bldgs = baseline_df[baseline_df[C_LOB].isin(scope_values)][C_BUILDING].nunique()
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
    end_ts   = pd.Timestamp(date_range[1])

    def _slice(df, weekdays=False):
        s = df[(df[C_DATE] >= start_ts) & (df[C_DATE] <= end_ts)]
        if weekdays:
            s = get_weekday_df(s)
        return s.groupby(C_DATE)[C_PREDICTED].sum()

    base_all  = _slice(baseline_df, weekdays=False)
    base_wday = _slice(baseline_df, weekdays=True)
    scen_wday = _slice(scenario_df,  weekdays=True)

    window_weekdays = int(base_wday.shape[0])
    window_days     = int(base_all.shape[0])

    return {
        "baseline_footfall":  int(base_all.sum()),
        "scenario_footfall":  int(_slice(scenario_df).sum()),
        "delta":              int(_slice(scenario_df).sum()) - int(base_all.sum()),
        "baseline_avg_daily": round(base_wday.sum() / window_weekdays) if window_weekdays else 0,
        "scenario_avg_daily": round(scen_wday.sum() / window_weekdays) if window_weekdays else 0,
        "window_days":        window_days,
        "window_weekdays":    window_weekdays,
    }


def compute_building_impact_table(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
) -> pd.DataFrame:
    start_ts = pd.Timestamp(date_range[0])
    end_ts   = pd.Timestamp(date_range[1])

    def agg(df):
        return (
            df[(df[C_DATE] >= start_ts) & (df[C_DATE] <= end_ts)]
            .groupby(C_BUILDING)[C_PREDICTED]
            .sum()
            .reset_index()
        )

    base_agg = agg(baseline_df).rename(columns={C_PREDICTED: "Baseline Forecast"})
    scen_agg = agg(scenario_df).rename(columns={C_PREDICTED: "Scenario Forecast"})
    merged = base_agg.merge(scen_agg, on=C_BUILDING)
    merged["Difference"] = merged["Scenario Forecast"] - merged["Baseline Forecast"]
    return merged.rename(columns={C_BUILDING: "Building"})[
        ["Building", "Baseline Forecast", "Scenario Forecast", "Difference"]
    ]


# ---------------------------------------------------------------------------
# Mode B — RTO Mandate & Seat Planning
# ---------------------------------------------------------------------------

def compute_rto_seat_plan(
    daily_df: pd.DataFrame,
    rto_pct: float,
    target_util: float,
) -> pd.DataFrame:
    """HC × RTO% → seats needed per LOB; gap vs current allocated seats.

    Args:
        daily_df:    Working DataFrame (must contain Headcount and Allocated Seats).
        rto_pct:     Fraction of HC expected in office (e.g. 0.60 = 60%).
        target_util: Planning buffer (e.g. 0.80 = plan for 80% seat utilization).

    Returns one row per LOB:
        LOB | Headcount | Expected Daily Demand | Allocated Seats | Seats Needed | Seat Gap | Status
    """
    if C_HEADCOUNT not in daily_df.columns or C_ALLOC not in daily_df.columns:
        return pd.DataFrame()

    hc = (
        daily_df.drop_duplicates(subset=C_LOB)
        [[C_LOB, C_HEADCOUNT]]
        .copy()
    )
    alloc = (
        daily_df.drop_duplicates(subset=[C_LOB, *FLOOR_KEY])
        .groupby(C_LOB)[C_ALLOC]
        .sum()
        .reset_index()
        .rename(columns={C_ALLOC: "Allocated Seats"})
    )
    df = hc.merge(alloc, on=C_LOB, how="left")
    df["Expected Daily Demand"] = (df[C_HEADCOUNT] * rto_pct).round().astype(int)
    df["Seats Needed"] = (
        df["Expected Daily Demand"] / max(target_util, 0.01)
    ).round().astype(int)
    df["Seat Gap"] = df["Allocated Seats"] - df["Seats Needed"]
    df["Status"]   = df["Seat Gap"].apply(
        lambda x: "✅ Surplus" if x >= 0 else "🔴 Deficit"
    )
    return df[[C_LOB, C_HEADCOUNT, "Expected Daily Demand", "Allocated Seats", "Seats Needed", "Seat Gap", "Status"]].sort_values("Seat Gap")


def compute_policy_kpis(
    daily_df: pd.DataFrame,
    rto_pct: float,
    target_util: float,
) -> dict:
    """Portfolio-level summary for Mode B RTO planning."""
    plan = compute_rto_seat_plan(daily_df, rto_pct, target_util)
    if plan.empty:
        return {"total_hc": 0, "expected_demand": 0, "total_allocated": 0,
                "total_seats_needed": 0, "portfolio_gap": 0}

    return {
        "total_hc":           int(plan[C_HEADCOUNT].sum()),
        "expected_demand":    int(plan["Expected Daily Demand"].sum()),
        "total_allocated":    int(plan["Allocated Seats"].sum()),
        "total_seats_needed": int(plan["Seats Needed"].sum()),
        "portfolio_gap":      int(plan["Seat Gap"].sum()),
    }


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def plot_daily_forecast(daily_df: pd.DataFrame, horizon_days: int = 30) -> go.Figure:
    """Line chart: portfolio daily predicted attendance vs total capacity."""
    df = get_horizon_df(daily_df, horizon_days)
    if df.empty:
        return go.Figure()

    bldg_day = _building_daily(df)
    daily = (
        bldg_day.groupby(C_DATE)
        .agg(predicted=("predicted_sum", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily[C_DATE], y=daily["predicted"],
        mode="lines", name="Predicted Attendance",
        line=dict(color="#1a3c5e", width=2),
        fill="tozeroy", fillcolor="rgba(26,60,94,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=daily[C_DATE], y=daily["capacity"],
        mode="lines", name="Total Capacity",
        line=dict(color="#dc3545", width=2, dash="dot"),
    ))
    fig.update_layout(
        title=f"Daily Predicted Attendance vs Capacity — Next {horizon_days} Days",
        xaxis_title="Date", yaxis_title="Seats",
        legend=dict(orientation="h", y=-0.2),
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig


def plot_dow_bar(dow_df: pd.DataFrame) -> go.Figure:
    """Bar chart: average attendance by day of week."""
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
        title="Avg Attendance by Day of Week (% Utilization)",
        xaxis_title="", yaxis_title="Avg Utilization %",
        yaxis=dict(range=[0, 115]),
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def plot_capacity_calendar(daily_df: pd.DataFrame, horizon_days: int = 30) -> go.Figure:
    """Calendar grid coloured by 4-tier utilization bands."""
    df = get_horizon_df(daily_df, horizon_days)
    if df.empty:
        return go.Figure()

    bldg_day = _building_daily(df)
    daily = (
        bldg_day.groupby(C_DATE)
        .agg(predicted=("predicted_sum", "sum"), capacity=("capacity", "sum"))
        .reset_index()
    )
    daily["util_pct"] = daily["predicted"] / daily["capacity"] * 100
    daily["dow"]  = daily[C_DATE].dt.dayofweek
    daily["week"] = daily[C_DATE].apply(lambda d: (d - daily[C_DATE].min()).days // 7)

    def cell_color(u, is_weekend):
        if is_weekend: return "#f0f0f0"
        if u > 85:     return "#e06c6c"
        if u > 75:     return "#f6c94e"
        if u > 60:     return "#a8d5a2"
        return "#dde8f0"

    def text_color(u, is_weekend):
        if is_weekend: return "#bbbbbb"
        if u > 85:     return "#7b1a1a"
        if u > 75:     return "#856404"
        if u > 60:     return "#155724"
        return "#4a6585"

    def tier_symbol(u, is_weekend):
        if is_weekend: return ""
        if u > 85:     return "▲"
        if u > 75:     return "!"
        if u > 60:     return "✓"
        return "↓"

    dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig = go.Figure()

    for _, row in daily.iterrows():
        week = int(row["week"])
        dow  = int(row["dow"])
        util = row["util_pct"]
        is_weekend = dow >= 5

        bg  = cell_color(util, is_weekend)
        fg  = text_color(util, is_weekend)
        sym = tier_symbol(util, is_weekend)
        cell_text = (
            row[C_DATE].strftime("%b %d") if is_weekend
            else f"{row[C_DATE].strftime('%b %d')}<br>{util:.0f}% {sym}"
        )

        fig.add_shape(
            type="rect",
            x0=dow - 0.45, x1=dow + 0.45,
            y0=week - 0.45, y1=week + 0.45,
            fillcolor=bg,
            line=dict(color="white", width=2),
        )
        fig.add_annotation(
            x=dow, y=week, text=cell_text,
            showarrow=False, font=dict(size=12, color=fg),
        )

    legend_items = [
        ("↓ <60% Under",     "#dde8f0", "#4a6585"),
        ("✓ 60–75% Healthy", "#a8d5a2", "#155724"),
        ("! 75–85% Watch",   "#f6c94e", "#856404"),
        ("▲ >85% Risk",      "#e06c6c", "#7b1a1a"),
    ]
    for i, (label, bg, fg) in enumerate(legend_items):
        fig.add_annotation(
            x=i * 1.75, y=-0.75, xref="x", yref="y",
            text=f"<span style='background:{bg};color:{fg};padding:2px 5px'>{label}</span>",
            showarrow=False, font=dict(size=11),
        )

    n_weeks = int(daily["week"].max()) + 1
    fig.update_layout(
        title=f"Capacity Calendar — Next {horizon_days} Days",
        xaxis=dict(tickmode="array", tickvals=list(range(7)), ticktext=dow_labels, range=[-0.6, 6.6]),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(n_weeks)),
            ticktext=[f"Wk {i+1}" for i in range(n_weeks)],
            range=[-0.6, n_weeks + 0.2],
            autorange="reversed",
        ),
        height=max(320, n_weeks * 100 + 60),
        margin=dict(l=50, r=10, t=40, b=10),
    )
    return fig


def plot_building_heatmap(monthly_df: pd.DataFrame) -> go.Figure:
    """Building × Month utilization heatmap with 4-tier discrete colour bands."""
    if monthly_df.empty:
        return go.Figure()

    month_order = (
        monthly_df[["month_label", "month_order"]]
        .drop_duplicates()
        .sort_values("month_order")["month_label"]
        .tolist()
    )
    pivot = monthly_df.pivot_table(
        index="building_name", columns="month_label",
        values="util_pct", aggfunc="mean",
    )
    cols_present = [c for c in month_order if c in pivot.columns]
    pivot = pivot[cols_present]
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

    n_buildings = len(pivot)

    COLORSCALE = [
        [0.000, "#dde8f0"], [0.599, "#dde8f0"],
        [0.600, "#a8d5a2"], [0.749, "#a8d5a2"],
        [0.750, "#f6c94e"], [0.849, "#f6c94e"],
        [0.850, "#e06c6c"], [1.000, "#c0392b"],
    ]
    z_values   = pivot.values
    text_matrix = [
        [f"{v:.0f}%\n{'↓' if v<60 else '✓' if v<75 else '!' if v<85 else '▲'}" if not pd.isna(v) else "" for v in row]
        for row in z_values
    ]

    fig = go.Figure(go.Heatmap(
        z=z_values, x=cols_present, y=pivot.index.tolist(),
        text=text_matrix, texttemplate="%{text}",
        colorscale=COLORSCALE, zmin=0, zmax=100,
        showscale=True,
        colorbar=dict(
            title="Util %",
            tickvals=[30, 60, 75, 85, 95],
            ticktext=["<60% Under", "60%", "75% Watch", "85%", ">85% Risk"],
            len=0.8,
        ),
        hovertemplate="<b>%{y}</b><br>%{x}<br>Utilization: %{z:.1f}%<extra></extra>",
    ))

    tier_labels = [
        ("◼ <60% Under-utilised", "#dde8f0", "#333"),
        ("◼ 60–75% Healthy",      "#a8d5a2", "#155724"),
        ("◼ 75–85% Watch",        "#f6c94e", "#856404"),
        ("◼ >85% Over-capacity",  "#e06c6c", "#7b1a1a"),
    ]
    for i, (label, bg, fg) in enumerate(tier_labels):
        fig.add_annotation(
            x=1.18, y=1.08 - i * 0.06, xref="paper", yref="paper",
            text=f"<span style='color:{fg}'>{label}</span>",
            showarrow=False, font=dict(size=10), xanchor="left",
        )

    fig.update_layout(
        title="Monthly Utilization by Building",
        height=max(320, n_buildings * 42 + 80),
        margin=dict(l=10, r=180, t=60, b=40),
        xaxis=dict(side="top", tickangle=-30),
        yaxis=dict(autorange="reversed"),
        font=dict(size=11),
    )
    fig.update_traces(textfont=dict(size=10, color="black"))
    return fig


def plot_scenario_wedge(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
    horizon_days: int = 60,
) -> go.Figure:
    """Baseline vs scenario split-line chart with shaded wedge."""
    today    = pd.Timestamp(get_data_anchor(baseline_df))
    end      = today + pd.Timedelta(days=horizon_days)
    start_ts = pd.Timestamp(date_range[0])
    end_ts   = pd.Timestamp(date_range[1])

    def daily_totals(df):
        return (
            df[(df[C_DATE] >= today) & (df[C_DATE] < end)]
            .groupby(C_DATE)[C_PREDICTED]
            .sum()
            .reset_index()
        )

    base  = daily_totals(baseline_df)
    scen  = daily_totals(scenario_df)
    merged = base.merge(scen, on=C_DATE, suffixes=("_base", "_scen"))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pd.concat([merged[C_DATE], merged[C_DATE][::-1]]),
        y=pd.concat([merged[f"{C_PREDICTED}_scen"], merged[f"{C_PREDICTED}_base"][::-1]]),
        fill="toself", fillcolor="rgba(26,60,94,0.10)",
        line=dict(color="rgba(255,255,255,0)"),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=merged[C_DATE], y=merged[f"{C_PREDICTED}_base"],
        mode="lines", name="Baseline",
        line=dict(color="#6c757d", width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=merged[C_DATE], y=merged[f"{C_PREDICTED}_scen"],
        mode="lines", name="Scenario",
        line=dict(color="#1a3c5e", width=2.5, dash="dash"),
    ))
    for dt in [start_ts, end_ts]:
        if today <= dt < end:
            fig.add_vline(x=dt, line_dash="dot", line_color="#ffc107", line_width=1.5)

    fig.update_layout(
        title="Scenario Impact — Baseline vs Adjusted Attendance",
        xaxis_title="Date", yaxis_title="Total Seats",
        legend=dict(orientation="h", y=-0.2),
        height=340,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig


def plot_rto_seat_plan(plan_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart: allocated seats vs seats needed per LOB."""
    if plan_df.empty:
        return go.Figure()

    lobs     = plan_df[C_LOB].tolist()
    needed   = plan_df["Seats Needed"].tolist()
    alloc    = plan_df["Allocated Seats"].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Allocated Seats", y=lobs, x=alloc,
        orientation="h",
        marker_color="#6c757d",
    ))
    fig.add_trace(go.Bar(
        name="Seats Needed (RTO plan)", y=lobs, x=needed,
        orientation="h",
        marker_color="#1a3c5e",
        opacity=0.85,
    ))
    fig.update_layout(
        barmode="overlay",
        title="Allocated Seats vs Seats Needed by LOB",
        xaxis_title="Seats", yaxis_title="",
        legend=dict(orientation="h", y=-0.2),
        height=max(280, len(lobs) * 40 + 80),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
