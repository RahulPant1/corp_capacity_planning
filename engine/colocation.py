"""Smart Unit Co-location Scoring — pairwise similarity analysis."""

from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np

from models.unit import Unit
from models.attendance import AttendanceProfile
from models.allocation import FloorAssignment
from config.defaults import (
    COLOCATION_WEIGHT_SIZE, COLOCATION_WEIGHT_GROWTH,
    COLOCATION_WEIGHT_SHIFT, COLOCATION_WEIGHT_RTO,
    COLOCATION_WEIGHT_PRIORITY, COLOCATION_TOP_PAIRS,
)

_PRIORITY_MAP = {"High": 1.0, "Medium": 0.5, "Low": 0.0, None: 0.25}


def _normalize_array(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize to [0, 1]. Returns zeros if range is zero."""
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-9:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


def compute_colocation_scores(
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    top_n: int = COLOCATION_TOP_PAIRS,
) -> List[dict]:
    """Compute pairwise co-location similarity scores for all unit pairs.

    Returns list of dicts sorted by score descending:
        unit_a, unit_b, score (0-1, higher = better match),
        dimensions (per-dimension similarities), reasoning
    """
    if len(units) < 2:
        return []

    w = {
        "size": COLOCATION_WEIGHT_SIZE,
        "growth": COLOCATION_WEIGHT_GROWTH,
        "shift": COLOCATION_WEIGHT_SHIFT,
        "rto": COLOCATION_WEIGHT_RTO,
        "priority": COLOCATION_WEIGHT_PRIORITY,
    }

    n = len(units)
    names = [u.unit_name for u in units]

    sizes = np.array([float(u.current_total_hc) for u in units])
    growths = np.array([u.hc_growth_pct for u in units])
    shifts = np.array([u.night_shift_pct for u in units])
    rto_days = np.array([
        attendance_map[u.unit_name].avg_rto_days_per_week
        if u.unit_name in attendance_map else 3.0
        for u in units
    ])
    priorities = np.array([_PRIORITY_MAP.get(u.business_priority, 0.25) for u in units])

    norm_sizes = _normalize_array(sizes)
    norm_growths = _normalize_array(growths)
    norm_shifts = _normalize_array(shifts)
    norm_rto = _normalize_array(rto_days)
    norm_prio = _normalize_array(priorities)

    dim_labels = {
        "size": "team size", "growth": "growth trajectory",
        "shift": "shift pattern", "rto": "RTO frequency",
        "priority": "business priority",
    }

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            dim_scores = {
                "size": 1.0 - abs(norm_sizes[i] - norm_sizes[j]),
                "growth": 1.0 - abs(norm_growths[i] - norm_growths[j]),
                "shift": 1.0 - abs(norm_shifts[i] - norm_shifts[j]),
                "rto": 1.0 - abs(norm_rto[i] - norm_rto[j]),
                "priority": 1.0 - abs(norm_prio[i] - norm_prio[j]),
            }

            score = sum(w[k] * dim_scores[k] for k in w)

            best_dim = max(dim_scores, key=dim_scores.get)
            worst_dim = min(dim_scores, key=dim_scores.get)
            reasoning = (
                f"Strong match on {dim_labels[best_dim]} "
                f"({dim_scores[best_dim]:.0%} similar). "
                f"Weakest on {dim_labels[worst_dim]} "
                f"({dim_scores[worst_dim]:.0%} similar)."
            )

            pairs.append({
                "unit_a": names[i],
                "unit_b": names[j],
                "score": round(score, 3),
                "dimensions": {k: round(v, 3) for k, v in dim_scores.items()},
                "reasoning": reasoning,
            })

    pairs.sort(key=lambda p: p["score"], reverse=True)
    return pairs[:top_n]


def get_current_colocations(
    assignments: List[FloorAssignment],
) -> List[dict]:
    """Identify units currently sharing the same floor.

    Returns list of dicts: floor_id, units, unit_count
    """
    floor_units = defaultdict(set)
    for a in assignments:
        fid = f"{a.tower_id}-F{a.floor_number}"
        floor_units[fid].add(a.unit_name)

    return [
        {"floor_id": fid, "units": sorted(unit_set), "unit_count": len(unit_set)}
        for fid, unit_set in sorted(floor_units.items())
        if len(unit_set) > 1
    ]


def flag_colocation_mismatches(
    current_colocations: List[dict],
    scores: List[dict],
    mismatch_threshold: float = 0.35,
) -> List[dict]:
    """Flag floor co-locations where units have low similarity scores."""
    score_lookup = {}
    for s in scores:
        key = tuple(sorted([s["unit_a"], s["unit_b"]]))
        score_lookup[key] = s["score"]

    mismatches = []
    for coloc in current_colocations:
        units = coloc["units"]
        for i in range(len(units)):
            for j in range(i + 1, len(units)):
                key = tuple(sorted([units[i], units[j]]))
                pair_score = score_lookup.get(key, 0.0)
                if pair_score < mismatch_threshold:
                    mismatches.append({
                        "floor_id": coloc["floor_id"],
                        "unit_a": units[i],
                        "unit_b": units[j],
                        "score": pair_score,
                        "flag_reason": (
                            f"Low co-location affinity ({pair_score:.0%}) — "
                            f"consider relocating to improve floor cohesion."
                        ),
                    })
    return mismatches
