"""Demand Forecasting Engine — trend, seasonality, probabilistic demand."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from config.defaults import (
    FORECAST_EMA_SPAN,
    FORECAST_CONFIDENCE_LEVELS,
    FORECAST_BOOTSTRAP_SAMPLES,
    DOW_OVERLOAD_FACTOR,
    HW_MIN_PERIODS,
    HW_SEASONAL_PERIODS,
)


# ── Private helpers ────────────────────────────────────────────────────────

def _fit_holt_winters(values: np.ndarray, seasonal_periods: int = 5) -> Optional[dict]:
    """Fit Holt-Winters additive ETS model. Returns result dict or None on failure."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    if len(values) < 2 * seasonal_periods:
        return None
    try:
        model = ExponentialSmoothing(
            values, trend="add", seasonal="add",
            seasonal_periods=seasonal_periods,
            damped_trend=True,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True, remove_bias=True)
        return {
            "hw_result": fit,
            "fitted_values": fit.fittedvalues,
            "residual_std": float(np.std(fit.resid)),
        }
    except Exception:
        return None


def _bday_steps_ahead(last_date, target_date) -> int:
    """Count business days from last_date (exclusive) to target_date (inclusive)."""
    return max(1, len(pd.bdate_range(last_date, target_date)) - 1)


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
    """Compute trend + EMA for a single unit.

    Tries Holt-Winters additive ETS (trend + weekly seasonality) first; falls back
    to linear regression if insufficient data or HW fitting fails.

    Returns dict with historical/forecast arrays, slope, model_type, mape, etc.
    Returns None if fewer than 7 data points.
    """
    unit_df = df[df["unit_name"] == unit_name].sort_values("date").copy()
    if len(unit_df) < 7:
        return None

    dates = pd.to_datetime(unit_df["date"].values)
    values = unit_df["in_office_count"].values.astype(float)

    # EMA always computed on the original series
    ema = pd.Series(values).ewm(span=FORECAST_EMA_SPAN, adjust=False).mean().values
    current_median = float(np.median(values[-30:]) if len(values) >= 30 else np.median(values))

    # ── Attempt Holt-Winters on business-day-aligned series ──────────────────
    bday_mask = pd.to_datetime(unit_df["date"]).dt.dayofweek < 5
    bday_df = unit_df[bday_mask].sort_values("date")

    hw_fit = None
    bday_values = None

    if len(bday_df) >= HW_MIN_PERIODS:
        bday_index = pd.bdate_range(bday_df["date"].iloc[0], bday_df["date"].iloc[-1])
        bday_series = (
            bday_df.set_index(pd.to_datetime(bday_df["date"]))["in_office_count"]
            .reindex(bday_index)
        )
        fill_ratio = bday_series.isna().sum() / len(bday_index) if len(bday_index) > 0 else 1.0
        if fill_ratio <= 0.20:
            bday_series = bday_series.ffill().bfill()
            bday_values = bday_series.values.astype(float)
            hw_fit = _fit_holt_winters(bday_values, HW_SEASONAL_PERIODS)

    if hw_fit is not None:
        # ── Holt-Winters forecast path ────────────────────────────────────────
        n_bdays = max(10, int(forecast_months * 21.7))
        hw_fcast = hw_fit["hw_result"].forecast(n_bdays)

        last_bday = pd.Timestamp(bday_df["date"].iloc[-1])
        forecast_dates = pd.bdate_range(
            start=last_bday + pd.Timedelta(days=1), periods=n_bdays
        )

        residual_std = hw_fit["residual_std"]
        steps = np.arange(1, n_bdays + 1)
        pi_width = 1.96 * residual_std * np.sqrt(steps / len(bday_values))
        hw_fcast_arr = hw_fcast.values
        forecast_upper = hw_fcast_arr + pi_width
        forecast_lower = np.maximum(0, hw_fcast_arr - pi_width)

        # Equivalent slope for backward compat with report generators
        fitted = hw_fit["fitted_values"].values
        hw_slope = (float(fitted[-1]) - float(fitted[0])) / len(fitted) if len(fitted) > 1 else 0.0

        # In-sample MAPE
        obs = bday_values[:len(fitted)]
        nonzero = obs != 0
        mape = float(np.mean(np.abs((obs[nonzero] - fitted[nonzero]) / obs[nonzero]))) if nonzero.any() else None

        mean_val = float(np.mean(fitted))
        trend_significant = abs(hw_slope) > 0.005 * mean_val if mean_val > 0 else False
        six_month_value = max(0.0, float(hw_fcast.iloc[-1]))

        return {
            "unit_name": unit_name,
            "historical_dates": dates,
            "historical_values": values,
            "trend_slope": hw_slope,
            "trend_intercept": float(fitted[0]),
            "ema_values": ema,
            "forecast_dates": forecast_dates,
            "forecast_median": hw_fcast_arr,
            "forecast_upper": forecast_upper,
            "forecast_lower": forecast_lower,
            "residual_std": residual_std,
            "trend_significant": trend_significant,
            "six_month_value": six_month_value,
            "current_median": current_median,
            "model_type": "holt_winters",
            "mape": mape,
        }

    # ── Linear regression fallback ────────────────────────────────────────────
    day_zero = dates[0]
    date_ints = np.array([(d - day_zero).days for d in dates])
    slope, intercept = np.polyfit(date_ints, values, 1)

    last_date = dates[-1]
    forecast_dates = pd.date_range(
        last_date + pd.Timedelta(days=1),
        periods=forecast_months * 30,
        freq="D",
    )
    future_day_ints = np.array([(d - day_zero).days for d in forecast_dates])
    forecast_trend = slope * future_day_ints + intercept

    residuals = values - (slope * date_ints + intercept)
    residual_std = float(np.std(residuals))

    forecast_upper = forecast_trend + 1.96 * residual_std
    forecast_lower = np.maximum(0, forecast_trend - 1.96 * residual_std)

    n = len(values)
    date_std = float(np.std(date_ints))
    slope_se = (residual_std / (date_std * np.sqrt(n))) if date_std > 0 else float("inf")
    t_stat = abs(slope) / slope_se if slope_se > 0 else 0.0
    trend_significant = t_stat > 1.5

    six_month_value = max(0.0, float(forecast_trend[-1]))

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
        "trend_significant": trend_significant,
        "six_month_value": six_month_value,
        "current_median": current_median,
        "model_type": "linear",
        "mape": None,
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

        current_median = round(float(np.median(recent)))
        current_peak = round(float(np.max(recent)))

        # End-of-period forecast (actual day ~180 value), floored at 0
        forecasted_median = max(0, round(float(fcast[-1])))
        forecasted_peak = max(0, round(float(np.max(fcast))))

        # 6-month change — absolute and % (bounded ±100%)
        six_month_change = forecasted_median - current_median
        if current_median > 0:
            raw_pct = (six_month_change / current_median) * 100.0
            six_month_change_pct = round(max(-100.0, min(200.0, raw_pct)), 1)
        else:
            six_month_change_pct = 0.0

        # Trend direction based on significance + magnitude
        if not trend["trend_significant"] or abs(six_month_change_pct) < 3:
            trend_direction = "→ Stable"
        elif six_month_change > 0:
            trend_direction = "↑ Growing"
        else:
            trend_direction = "↓ Declining"

        summaries.append({
            "unit_name": name,
            "current_median": current_median,
            "current_peak": current_peak,
            "forecasted_median": forecasted_median,
            "forecasted_peak": forecasted_peak,
            "six_month_change": six_month_change,
            "six_month_change_pct": six_month_change_pct,
            "trend_direction": trend_direction,
            # Fraction form of 6m change % — used by "Apply" button for hc_growth_pct
            "suggested_growth_pct": six_month_change_pct / 100.0,
        })

    return summaries


# ── Week-Ahead Operational Forecast ──────────────────────────────────────

def compute_week_ahead_forecast(
    df: pd.DataFrame,
    total_capacity: int = 0,
    n_days: int = 5,
    holiday_dates: Optional[List[str]] = None,
) -> List[dict]:
    """Working-day attendance forecast using per-unit Holt-Winters ETS.

    Uses per-unit HW models where available; falls back to DOW medians + aggregate
    trend slope for units with insufficient data.

    Args:
        n_days: Number of upcoming business days to forecast (default 5).
        holiday_dates: Optional list of date strings (YYYY-MM-DD) to skip.

    Returns list of dicts per working day:
        date, weekday_name, short_label, expected_seats, capacity_pct, status
    Returns [] if insufficient data (< 7 weekday records).
    """
    from datetime import datetime, timedelta

    dow_df = compute_dow_patterns(df)
    if dow_df.empty:
        return []

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
    upcoming: List = []
    d = today + timedelta(days=1)
    while len(upcoming) < n_days:
        if d.weekday() < 5 and d not in holiday_set:
            upcoming.append(d)
        d += timedelta(days=1)

    # Per-unit HW models + DOW fallback data
    unit_names = df["unit_name"].unique()
    unit_hw: dict = {}    # {unit: hw_fit or None}
    unit_last: dict = {}  # {unit: last observed business day Timestamp}
    unit_dow: dict = {}   # {unit: {dow_int: median}}

    for unit in unit_names:
        unit_rows = dow_df[dow_df["unit_name"] == unit]
        unit_dow[unit] = dict(zip(
            unit_rows["day_of_week"].astype(int),
            unit_rows["median_count"].astype(float),
        ))
        udf = df[df["unit_name"] == unit].sort_values("date")
        bday_mask = pd.to_datetime(udf["date"]).dt.dayofweek < 5
        bdays = udf[bday_mask]
        if len(bdays) < HW_MIN_PERIODS:
            unit_hw[unit] = None
            continue
        bday_values = bdays["in_office_count"].values.astype(float)
        hw_fit = _fit_holt_winters(bday_values, HW_SEASONAL_PERIODS)
        unit_hw[unit] = hw_fit
        if hw_fit is not None:
            unit_last[unit] = pd.Timestamp(bdays["date"].iloc[-1])

    # Fallback: aggregate linear slope
    overall = compute_overall_trend(df)
    fallback_slope = overall.get("trend_slope", 0.0) if overall else 0.0

    results = []
    for i, day in enumerate(upcoming):
        total_expected = 0.0
        for unit in unit_names:
            hw_fit = unit_hw.get(unit)
            if hw_fit is not None and unit in unit_last:
                steps = _bday_steps_ahead(unit_last[unit], pd.Timestamp(day))
                total_expected += max(0.0, float(hw_fit["hw_result"].forecast(steps).iloc[-1]))
            else:
                total_expected += max(
                    0.0,
                    unit_dow.get(unit, {}).get(day.weekday(), 0.0) + fallback_slope * (i + 1),
                )

        expected = max(0, round(total_expected))
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

    Uses per-unit Holt-Winters ETS where available; falls back to DOW medians +
    unit-level trend slope for units with insufficient data.

    Returns List[dict]: unit_name, date, short_label, weekday_name, expected_seats.
    Returns [] if insufficient data.
    """
    from datetime import datetime, timedelta

    dow_df = compute_dow_patterns(df)
    if dow_df.empty:
        return []

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

    # Per-unit HW models + fallback data
    unit_names = df["unit_name"].unique()
    unit_hw: dict = {}    # {unit: hw_fit or None}
    unit_last: dict = {}  # {unit: last observed business day Timestamp}
    unit_dow: dict = {}   # {unit: {dow_int: median}}
    unit_slopes: dict = {}  # {unit: fallback linear slope}

    for unit in unit_names:
        unit_rows = dow_df[dow_df["unit_name"] == unit]
        unit_dow[unit] = dict(zip(
            unit_rows["day_of_week"].astype(int),
            unit_rows["median_count"].astype(float),
        ))
        trend = compute_unit_trend(df, unit, forecast_months=1)
        unit_slopes[unit] = trend["trend_slope"] if trend else 0.0

        udf = df[df["unit_name"] == unit].sort_values("date")
        bday_mask = pd.to_datetime(udf["date"]).dt.dayofweek < 5
        bdays = udf[bday_mask]
        if len(bdays) < HW_MIN_PERIODS:
            unit_hw[unit] = None
            continue
        bday_values = bdays["in_office_count"].values.astype(float)
        hw_fit = _fit_holt_winters(bday_values, HW_SEASONAL_PERIODS)
        unit_hw[unit] = hw_fit
        if hw_fit is not None:
            unit_last[unit] = pd.Timestamp(bdays["date"].iloc[-1])

    results = []
    for i, day in enumerate(upcoming):
        for unit in unit_names:
            hw_fit = unit_hw.get(unit)
            if hw_fit is not None and unit in unit_last:
                steps = _bday_steps_ahead(unit_last[unit], pd.Timestamp(day))
                expected = max(0, round(float(hw_fit["hw_result"].forecast(steps).iloc[-1])))
            else:
                base = unit_dow.get(unit, {}).get(day.weekday(), 0.0)
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
