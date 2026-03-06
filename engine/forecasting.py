"""Demand Forecasting Engine — trend, seasonality, probabilistic demand."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from config.defaults import (
    FORECAST_EMA_SPAN,
    FORECAST_CONFIDENCE_LEVELS,
    FORECAST_BOOTSTRAP_SAMPLES,
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
