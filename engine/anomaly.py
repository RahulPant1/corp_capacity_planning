"""Attendance Anomaly Detection — z-score based flagging of unusual patterns."""

from typing import Dict, List
import numpy as np

from models.unit import Unit
from models.attendance import AttendanceProfile
from config.defaults import ANOMALY_Z_SCORE_THRESHOLD, ANOMALY_MIN_UNITS


def _safe_z_scores(values: np.ndarray) -> np.ndarray:
    """Compute z-scores, returning zeros if std is near zero or too few values."""
    if len(values) < ANOMALY_MIN_UNITS:
        return np.zeros_like(values)
    std = values.std()
    if std < 1e-9:
        return np.zeros_like(values)
    return (values - values.mean()) / std


def detect_attendance_anomalies(
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    z_threshold: float = ANOMALY_Z_SCORE_THRESHOLD,
) -> List[dict]:
    """Flag units with unusual attendance patterns using z-scores.

    Metrics checked:
    - peak_to_median_ratio: spiky attendance
    - avg_rto_days_per_week: unusually high or low office presence
    - median_hc vs current_total_hc ratio: data quality signal

    Returns list of dicts sorted by absolute z-score descending:
        unit_name, metric, value, z_score, direction, anomaly_type, recommendation
    """
    matched = [(u, attendance_map[u.unit_name])
               for u in units if u.unit_name in attendance_map]

    if len(matched) < ANOMALY_MIN_UNITS:
        return []

    names = [u.unit_name for u, _ in matched]

    peak_ratios = np.array([att.peak_to_median_ratio for _, att in matched])
    rto_days = np.array([att.avg_rto_days_per_week for _, att in matched])
    hc_ratios = np.array([
        att.monthly_median_hc / u.current_total_hc
        if u.current_total_hc > 0 else 1.0
        for u, att in matched
    ])

    z_peak = _safe_z_scores(peak_ratios)
    z_rto = _safe_z_scores(rto_days)
    z_hc = _safe_z_scores(hc_ratios)

    anomalies = []
    for i, name in enumerate(names):
        if abs(z_peak[i]) > z_threshold:
            direction = "high" if z_peak[i] > 0 else "low"
            anomalies.append({
                "unit_name": name,
                "metric": "Peak-to-Median Ratio",
                "value": round(float(peak_ratios[i]), 2),
                "z_score": round(float(z_peak[i]), 2),
                "direction": direction,
                "anomaly_type": (
                    "Unusually high peak-to-median"
                    if direction == "high"
                    else "Unusually low peak-to-median"
                ),
                "recommendation": (
                    "Spiky attendance pattern — consider larger peak buffer or flexible seating."
                    if direction == "high"
                    else "Very flat attendance pattern — may benefit from reduced seat allocation."
                ),
            })

        if abs(z_rto[i]) > z_threshold:
            direction = "high" if z_rto[i] > 0 else "low"
            anomalies.append({
                "unit_name": name,
                "metric": "Avg RTO Days/Week",
                "value": round(float(rto_days[i]), 1),
                "z_score": round(float(z_rto[i]), 2),
                "direction": direction,
                "anomaly_type": (
                    "Unusually high RTO"
                    if direction == "high"
                    else "Unusually low RTO"
                ),
                "recommendation": (
                    "Always in office — verify this unit needs all allocated seats daily."
                    if direction == "high"
                    else "Rarely in office — significant hot-desking opportunity."
                ),
            })

        if abs(z_hc[i]) > z_threshold:
            direction = "high" if z_hc[i] > 0 else "low"
            anomalies.append({
                "unit_name": name,
                "metric": "Median HC / Current HC",
                "value": round(float(hc_ratios[i]), 2),
                "z_score": round(float(z_hc[i]), 2),
                "direction": direction,
                "anomaly_type": "Median HC far from current HC",
                "recommendation": (
                    "Attendance median is much higher than expected — "
                    "verify headcount data is accurate."
                    if direction == "high"
                    else "Attendance median is much lower than headcount — "
                    "possible data quality issue or large remote-only segment."
                ),
            })

    anomalies.sort(key=lambda a: abs(a["z_score"]), reverse=True)
    return anomalies


def get_anomaly_summary(anomalies: List[dict]) -> dict:
    """Summarize anomalies for dashboard display."""
    if not anomalies:
        return {"total_anomalies": 0, "units_flagged": 0, "by_type": {}}

    units_flagged = len(set(a["unit_name"] for a in anomalies))
    by_type = {}
    for a in anomalies:
        by_type[a["anomaly_type"]] = by_type.get(a["anomaly_type"], 0) + 1

    return {
        "total_anomalies": len(anomalies),
        "units_flagged": units_flagged,
        "by_type": by_type,
    }
