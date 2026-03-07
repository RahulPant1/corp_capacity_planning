"""Demand Forecasting Engine — trend, seasonality, probabilistic demand."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from config.defaults import (
    FORECAST_EMA_SPAN,
    FORECAST_CONFIDENCE_LEVELS,
    FORECAST_BOOTSTRAP_SAMPLES,
    DOW_OVERLOAD_FACTOR,
)


# ── Trend Analysis ─────────────────────────────────────────────────────────

def compute_overall_trend(
    df: pd.DataFrame,
    forecast_months: int = 6,
) -> Optional[dict]:
    """Compute trend for total attendance across all units (summed per date).

    Same return structure as compute_unit_trend with unit_name="All Units".
    """
    agg = df.groupby("date")["in_office_count"].sum().reset_index()
    agg.columns = ["date", "in_office_count"]
    agg["unit_name"] = "All Units"
    return compute_unit_trend(agg, "All Units", forecast_months)


def compute_unit_trend(
    df: pd.DataFrame,
    unit_name: str,
    forecast_months: int = 6,
) -> Optional[dict]:
    """Compute linear trend + EMA for a single unit.

    Returns dict with historical/forecast arrays, slope, suggested_growth_pct.
    Returns None if fewer than 7 data points.
    """
    unit_df = df[df["unit_name"] == unit_name].sort_values("date").copy()
    if len(unit_df) < 7:
        return None

    dates = pd.to_datetime(unit_df["date"].values)
    values = unit_df["in_office_count"].values.astype(float)

    # Convert to integer days from start for regression
    day_zero = dates[0]
    date_ints = np.array([(d - day_zero).days for d in dates])

    # Linear regression (degree 1)
    slope, intercept = np.polyfit(date_ints, values, 1)

    # Exponential moving average
    ema = pd.Series(values).ewm(span=FORECAST_EMA_SPAN, adjust=False).mean().values

    # Project forward
    last_date = dates[-1]
    forecast_dates = pd.date_range(
        last_date + pd.Timedelta(days=1),
        periods=forecast_months * 30,
        freq="D",
    )
    future_day_ints = np.array([(d - day_zero).days for d in forecast_dates])
    forecast_trend = slope * future_day_ints + intercept

    # Residual std for confidence bands
    residuals = values - (slope * date_ints + intercept)
    residual_std = float(np.std(residuals))

    forecast_upper = forecast_trend + 1.96 * residual_std
    forecast_lower = np.maximum(0, forecast_trend - 1.96 * residual_std)

    # Suggested annual growth % from slope
    current_median = float(np.median(values[-30:]) if len(values) >= 30 else np.median(values))
    if current_median > 0:
        annual_growth_pct = (slope / current_median) * 365
    else:
        annual_growth_pct = 0.0

    return {
        "unit_name": unit_name,
        "historical_dates": dates,
        "historical_values": values,
        "trend_slope": float(slope),
        "trend_intercept": float(intercept),
        "ema_values": ema,
        "forecast_dates": forecast_dates,
        "forecast_median": forecast_trend,
        "forecast_upper": forecast_upper,
        "forecast_lower": forecast_lower,
        "residual_std": residual_std,
        "suggested_growth_pct": round(annual_growth_pct, 4),
        "current_median": current_median,
    }


# ── Seasonality: Day-of-Week Patterns ─────────────────────────────────────

def compute_dow_patterns(
    df: pd.DataFrame,
    unit_name: Optional[str] = None,
) -> pd.DataFrame:
    """Compute day-of-week attendance patterns (weekdays only).

    Returns DataFrame: unit_name, day_of_week, day_name, mean/median/std/min/max.
    """
    work_df = df.copy()
    work_df["day_of_week"] = pd.to_datetime(work_df["date"]).dt.dayofweek
    work_df = work_df[work_df["day_of_week"] < 5]  # Weekdays only

    if unit_name:
        work_df = work_df[work_df["unit_name"] == unit_name]

    if work_df.empty:
        return pd.DataFrame()

    agg = work_df.groupby(["unit_name", "day_of_week"])["in_office_count"].agg(
        ["mean", "median", "std", "min", "max"]
    ).reset_index()
    agg.columns = [
        "unit_name", "day_of_week",
        "mean_count", "median_count", "std_count", "min_count", "max_count",
    ]

    day_names = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    agg["day_name"] = agg["day_of_week"].map(day_names)

    return agg


# ── Probabilistic Seat Demand ─────────────────────────────────────────────

def compute_percentile_demand(
    df: pd.DataFrame,
    unit_name: str,
    confidence_levels: Optional[List[float]] = None,
) -> Optional[dict]:
    """Compute seat demand at various confidence levels from daily data.

    Returns dict with median, mean, peak, percentiles, savings_vs_peak.
    """
    if confidence_levels is None:
        confidence_levels = FORECAST_CONFIDENCE_LEVELS

    unit_df = df[df["unit_name"] == unit_name]
    values = unit_df["in_office_count"].values

    if len(values) < 10:
        return None

    median_val = float(np.median(values))
    mean_val = float(np.mean(values))
    peak_val = float(np.max(values))

    percentiles = {}
    savings = {}
    for cl in confidence_levels:
        p_val = float(np.percentile(values, cl * 100))
        percentiles[cl] = round(p_val)
        savings[cl] = round(peak_val - p_val)

    return {
        "unit_name": unit_name,
        "median": round(median_val),
        "mean": round(mean_val),
        "peak": round(peak_val),
        "percentiles": percentiles,
        "savings_vs_peak": savings,
        "n_observations": len(values),
    }


def bootstrap_confidence_interval(
    df: pd.DataFrame,
    unit_name: str,
    confidence_level: float = 0.95,
    n_bootstrap: int = FORECAST_BOOTSTRAP_SAMPLES,
    seed: int = 42,
) -> Optional[dict]:
    """Bootstrap Monte Carlo for CI on demand percentile estimate.

    Resamples daily attendance with replacement, computes the chosen
    percentile on each sample, reports the CI of that percentile.
    """
    rng = np.random.RandomState(seed)
    unit_df = df[df["unit_name"] == unit_name]
    values = unit_df["in_office_count"].values

    if len(values) < 20:
        return None

    target_percentile = confidence_level * 100
    bootstrap_estimates = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        sample = rng.choice(values, size=len(values), replace=True)
        bootstrap_estimates[i] = np.percentile(sample, target_percentile)

    point_estimate = float(np.percentile(values, target_percentile))

    return {
        "unit_name": unit_name,
        "confidence_level": confidence_level,
        "point_estimate": round(point_estimate),
        "ci_lower": round(float(np.percentile(bootstrap_estimates, 2.5))),
        "ci_upper": round(float(np.percentile(bootstrap_estimates, 97.5))),
        "bootstrap_std": round(float(np.std(bootstrap_estimates)), 1),
    }


# ── Forecast Summary ──────────────────────────────────────────────────────

def compute_forecast_summary(
    df: pd.DataFrame,
    unit_names: List[str],
    forecast_months: int = 6,
) -> List[dict]:
    """Compute forecast summary for all units."""
    summaries = []
    for name in unit_names:
        trend = compute_unit_trend(df, name, forecast_months)
        if trend is None:
            continue

        unit_df = df[df["unit_name"] == name]
        values = unit_df["in_office_count"].values
        recent = values[-30:] if len(values) >= 30 else values

        fcast = trend["forecast_median"]

        summaries.append({
            "unit_name": name,
            "current_median": round(float(np.median(recent))),
            "current_peak": round(float(np.max(recent))),
            "forecasted_median": round(float(np.median(fcast))),
            "forecasted_peak": round(float(np.max(fcast))),
            "suggested_growth_pct": trend["suggested_growth_pct"],
        })

    return summaries


# ── Week-Ahead Operational Forecast ──────────────────────────────────────

def compute_week_ahead_forecast(
    df: pd.DataFrame,
    total_capacity: int = 0,
    n_days: int = 5,
    holiday_dates: Optional[List[str]] = None,
) -> List[dict]:
    """Working-day attendance forecast using DOW patterns + overall trend.

    Uses historical day-of-week medians (summed across all units) and applies
    the overall trend slope as a recency adjustment.

    Args:
        n_days: Number of upcoming business days to forecast (default 5).
        holiday_dates: Optional list of date strings (YYYY-MM-DD) to skip.

    Returns list of dicts per working day:
        date, weekday_name, short_label, expected_seats, capacity_pct, status
    Returns [] if insufficient data (< 7 weekday records).
    """
    from datetime import datetime, timedelta

    dow_df = compute_dow_patterns(df)  # all units, all weekdays
    if dow_df.empty:
        return []

    overall = compute_overall_trend(df)
    slope = overall.get("trend_slope", 0.0) if overall else 0.0

    # Sum medians across all units per weekday
    dow_totals = (
        dow_df.groupby("day_of_week")["median_count"]
        .sum()
        .to_dict()
    )

    # Build holiday set for fast lookup
    holiday_set = set()
    if holiday_dates:
        for h in holiday_dates:
            try:
                holiday_set.add(pd.Timestamp(h).date())
            except Exception:
                pass

    # Find next n_days working days, skipping holidays
    today = datetime.now().date()
    upcoming: List = []
    d = today + timedelta(days=1)
    while len(upcoming) < n_days:
        if d.weekday() < 5 and d not in holiday_set:
            upcoming.append(d)
        d += timedelta(days=1)

    results = []
    for i, day in enumerate(upcoming):
        base = dow_totals.get(day.weekday(), 0)
        expected = max(0, round(base + slope * (i + 1)))
        cap_pct = expected / total_capacity if total_capacity > 0 else 0.0
        status = "HIGH" if cap_pct > 0.85 else ("MEDIUM" if cap_pct > 0.65 else "LOW")
        results.append({
            "date": day,
            "weekday_name": day.strftime("%A"),
            "short_label": day.strftime("%a\n%b %d"),
            "expected_seats": expected,
            "capacity_pct": cap_pct,
            "status": status,
        })
    return results


def compute_per_unit_forecast(
    df: pd.DataFrame,
    n_days: int = 5,
    holiday_dates: Optional[List[str]] = None,
) -> List[dict]:
    """Per-unit attendance forecast for the next n_days business days.

    Uses per-unit DOW medians + unit-level trend slope as recency adjustment.

    Returns List[dict]: unit_name, date, short_label, weekday_name, expected_seats.
    Returns [] if insufficient data.
    """
    from datetime import datetime, timedelta

    dow_df = compute_dow_patterns(df)
    if dow_df.empty:
        return []

    # Build per-unit DOW medians: {unit_name: {dow_int: median}}
    unit_dow: dict = {}
    for _, row in dow_df.iterrows():
        unit_dow.setdefault(row["unit_name"], {})[int(row["day_of_week"])] = float(row["median_count"])

    # Per-unit trend slopes
    unit_slopes: dict = {}
    for unit in unit_dow:
        trend = compute_unit_trend(df, unit, forecast_months=1)
        unit_slopes[unit] = trend["trend_slope"] if trend else 0.0

    # Build holiday set
    holiday_set = set()
    if holiday_dates:
        for h in holiday_dates:
            try:
                holiday_set.add(pd.Timestamp(h).date())
            except Exception:
                pass

    # Find next n_days business days
    today = datetime.now().date()
    upcoming = []
    d = today + timedelta(days=1)
    while len(upcoming) < n_days:
        if d.weekday() < 5 and d not in holiday_set:
            upcoming.append(d)
        d += timedelta(days=1)

    results = []
    for i, day in enumerate(upcoming):
        for unit, dow_medians in unit_dow.items():
            base = dow_medians.get(day.weekday(), 0.0)
            slope = unit_slopes.get(unit, 0.0)
            expected = max(0, round(base + slope * (i + 1)))
            results.append({
                "unit_name": unit,
                "date": day,
                "short_label": day.strftime("%a %b %d"),
                "weekday_name": day.strftime("%A"),
                "expected_seats": expected,
            })

    return results


def compute_peak_day_per_unit(df: pd.DataFrame) -> List[dict]:
    """Identify the peak day-of-week for each unit based on historical medians.

    Returns List[dict]: unit_name, peak_day_name, peak_day_median, overall_median, peak_ratio.
    """
    dow_df = compute_dow_patterns(df)
    if dow_df.empty:
        return []

    results = []
    for unit_name in dow_df["unit_name"].unique():
        unit_dow = dow_df[dow_df["unit_name"] == unit_name]
        if unit_dow.empty:
            continue
        peak_row = unit_dow.loc[unit_dow["median_count"].idxmax()]
        overall_median = float(unit_dow["median_count"].mean())
        peak_median = float(peak_row["median_count"])
        peak_ratio = round(peak_median / overall_median, 2) if overall_median > 0 else 1.0
        results.append({
            "unit_name": unit_name,
            "peak_day_name": peak_row["day_name"],
            "peak_day_median": round(peak_median),
            "overall_median": round(overall_median),
            "peak_ratio": peak_ratio,
        })

    return results


def compute_dow_conflict_analysis(df: pd.DataFrame) -> dict:
    """Detect cross-unit peak day conflicts and generate stagger suggestions.

    Identifies days where company-wide load significantly exceeds average
    (by DOW_OVERLOAD_FACTOR), then suggests alternative days per unit.

    Returns dict with:
        day_loads: {day_name: total_median_seats}  (Mon–Fri)
        peak_units_by_day: {day_name: [unit_name, ...]}
        suggestions: List[dict] — unit_name, current_peak_day, suggested_day, load_reduction
        overloaded_days: List[str]
    """
    peak_data = compute_peak_day_per_unit(df)
    if not peak_data:
        return {"day_loads": {}, "peak_units_by_day": {}, "suggestions": [], "overloaded_days": []}

    dow_df = compute_dow_patterns(df)
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    # Company-wide load per day (sum of all unit medians for each day)
    day_totals: dict = {d: 0.0 for d in day_order}
    # Per-unit DOW medians: {unit_name: {day_name: median}}
    unit_day_medians: dict = {}
    for _, row in dow_df.iterrows():
        unit = row["unit_name"]
        day = row["day_name"]
        median = float(row["median_count"])
        day_totals[day] = day_totals.get(day, 0.0) + median
        unit_day_medians.setdefault(unit, {})[day] = median

    # Identify overloaded days
    valid_loads = [v for v in day_totals.values() if v > 0]
    if not valid_loads:
        return {"day_loads": day_totals, "peak_units_by_day": {}, "suggestions": [], "overloaded_days": []}

    mean_load = float(np.mean(valid_loads))
    overloaded_days = [d for d in day_order if day_totals.get(d, 0) > mean_load * DOW_OVERLOAD_FACTOR]

    # Peak units by day (all days, not just overloaded)
    peak_by_day: dict = {d: [] for d in day_order}
    for p in peak_data:
        peak_by_day[p["peak_day_name"]].append(p["unit_name"])

    # Stagger suggestions: for each unit peaking on an overloaded day,
    # suggest the lowest company-load alternative day
    suggestions = []
    for p in peak_data:
        unit = p["unit_name"]
        current_peak_day = p["peak_day_name"]
        if current_peak_day not in overloaded_days:
            continue

        unit_days = unit_day_medians.get(unit, {})
        alternatives = [(d, day_totals.get(d, 0.0)) for d in day_order if d != current_peak_day]
        alternatives.sort(key=lambda x: x[1])  # sort by company-wide load ascending

        if not alternatives:
            continue

        suggested_day = alternatives[0][0]
        load_on_peak = unit_days.get(current_peak_day, 0.0)
        suggestions.append({
            "unit_name": unit,
            "current_peak_day": current_peak_day,
            "suggested_day": suggested_day,
            "load_reduction": round(load_on_peak),
        })

    return {
        "day_loads": {d: round(day_totals.get(d, 0)) for d in day_order},
        "peak_units_by_day": {d: v for d, v in peak_by_day.items() if v},
        "suggestions": suggestions,
        "overloaded_days": overloaded_days,
    }


# ── Demand Correlation ────────────────────────────────────────────────────

def compute_demand_correlation(
    df: pd.DataFrame,
    unit_names: List[str],
) -> pd.DataFrame:
    """Pairwise Pearson correlation of daily attendance between units."""
    pivot = df.pivot_table(
        index="date", columns="unit_name",
        values="in_office_count", aggfunc="sum",
    )
    valid = [u for u in unit_names if u in pivot.columns]
    if len(valid) < 2:
        return pd.DataFrame()
    pivot = pivot[valid].dropna()
    return pivot.corr()


# ── Capacity Breach Probability ───────────────────────────────────────────

def compute_capacity_breach_probability(
    df: pd.DataFrame,
    unit_name: str,
    allocated_seats: int,
) -> Optional[dict]:
    """Probability that daily demand exceeds allocated seats."""
    unit_df = df[df["unit_name"] == unit_name]
    values = unit_df["in_office_count"].values

    if len(values) < 10:
        return None

    breaches = values > allocated_seats
    breach_prob = float(np.mean(breaches))
    breach_magnitudes = values[breaches] - allocated_seats
    avg_magnitude = float(np.mean(breach_magnitudes)) if len(breach_magnitudes) > 0 else 0

    return {
        "unit_name": unit_name,
        "allocated_seats": allocated_seats,
        "breach_probability": round(breach_prob, 4),
        "expected_breach_days_per_month": round(breach_prob * 22, 1),
        "avg_breach_magnitude": round(avg_magnitude),
    }


# ── Temporal Clustering ──────────────────────────────────────────────────

def compute_temporal_clustering(
    df: pd.DataFrame,
    unit_names: List[str],
    threshold: float = 0.7,
) -> List[dict]:
    """Cluster units by temporal attendance similarity.

    Uses correlation threshold — units with corr > threshold are grouped.
    """
    corr = compute_demand_correlation(df, unit_names)
    if corr.empty or len(corr) < 2:
        return []

    visited = set()
    clusters = []
    cluster_id = 0

    for unit in corr.columns:
        if unit in visited:
            continue
        cluster = [unit]
        visited.add(unit)
        for other in corr.columns:
            if other not in visited and corr.loc[unit, other] > threshold:
                cluster.append(other)
                visited.add(other)
        clusters.append((cluster_id, cluster))
        cluster_id += 1

    results = []
    for cid, members in clusters:
        for unit in members:
            results.append({
                "unit_name": unit,
                "cluster_id": cid,
                "cluster_label": f"Group {cid + 1}",
                "cluster_size": len(members),
            })

    return results
