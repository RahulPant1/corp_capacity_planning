"""Scenario Comparison Engine — batch-run parameter matrix and rank results."""

import copy
import itertools
from typing import Dict, List, Optional

from models.unit import Unit
from models.attendance import AttendanceProfile
from models.building import Floor
from models.scenario import Scenario, ScenarioParams
from engine.scenario_engine import run_scenario, apply_floor_modifications
from engine.optimizer import optimize_allocation


def run_scenario_matrix(
    base_scenario: Scenario,
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    floors: List[Floor],
    rule_config: dict,
    param_grid: dict,
    max_floors_per_unit: int = 3,
    min_guarantee_pct: float = 0.80,
) -> List[dict]:
    """Run all parameter combinations and return a list of result dicts.

    param_grid keys (all optional):
        "alloc_pct"    → List[float]  e.g. [0.70, 0.80, 0.90]
        "rto_mandate"  → List[float]  e.g. [2.0, 3.0, 4.0]
        "cap_red"      → List[float]  e.g. [0.0, 0.10]
        "objective"    → List[str]    e.g. ["optimal_placement", "rto_based"]

    Returns list of dicts, one per combination, with params + outcome metrics.
    """
    alloc_values   = param_grid.get("alloc_pct",   [rule_config.get("global_alloc_pct", 0.80)])
    rto_values     = param_grid.get("rto_mandate",  [base_scenario.params.global_rto_mandate_days or 3.0])
    capred_values  = param_grid.get("cap_red",      [base_scenario.params.capacity_reduction_pct or 0.0])
    obj_values     = param_grid.get("objective",    ["optimal_placement"])

    results = []
    idx = 0

    for alloc, rto, cap_red, objective in itertools.product(
        alloc_values, rto_values, capred_values, obj_values
    ):
        idx += 1
        rc = dict(rule_config)
        # RTO-Based mode ignores alloc% — mark as N/A
        if objective != "rto_based":
            rc["global_alloc_pct"] = alloc
            effective_alloc = alloc
        else:
            effective_alloc = None  # attendance-driven

        rto_mandate_val = rto if objective == "optimal_placement" else None
        target_rto_val  = rto if objective == "rto_whatif" else None

        # Build temp scenario
        temp = copy.deepcopy(base_scenario)
        temp.params = ScenarioParams(
            global_rto_mandate_days=rto_mandate_val,
            capacity_reduction_pct=cap_red,
            excluded_floors=base_scenario.params.excluded_floors,
        )

        # Simulation
        try:
            temp = run_scenario(temp, units, attendance_map, floors, rc)
        except Exception as exc:
            results.append(_error_result(idx, effective_alloc, rto, cap_red, objective, str(exc)))
            continue

        # Collect simulation metrics
        demand = sum(a.effective_demand_seats for a in temp.allocation_results)
        eff_floors = apply_floor_modifications(floors, temp)
        capacity = sum(f.total_seats for f in eff_floors)
        headroom = capacity - demand
        total_gap = sum(a.seat_gap for a in temp.allocation_results)
        units_at_risk = sum(1 for a in temp.allocation_results if a.seat_gap < 0)
        avg_frag = (
            sum(a.fragmentation_score for a in temp.allocation_results) / len(temp.allocation_results)
            if temp.allocation_results else 0.0
        )

        # Optimization
        try:
            opt_result = optimize_allocation(
                allocations=temp.allocation_results,
                floors=eff_floors,
                baseline_assignments=base_scenario.floor_assignments,
                objective=objective,
                excluded_floor_ids=[],
                units=units,
                attendance_map=attendance_map,
                rule_config=rc,
                target_rto_days=target_rto_val,
                max_floors_per_unit=max_floors_per_unit,
                min_guarantee_pct=min_guarantee_pct,
            )
            opt_seats = sum(opt_result.unit_allocations.values())
            floors_used = len(set(
                (a.tower_id, a.floor_number) for a in opt_result.assignments
            ))
            seats_saved = (
                opt_result.savings_summary.get("seats_saved", 0)
                if opt_result.savings_summary else 0
            )
            opt_status = opt_result.status
            # Store assignments for potential adoption
            opt_assignments = opt_result.assignments
            opt_unit_allocations = opt_result.unit_allocations
        except Exception as exc:
            opt_seats = demand
            floors_used = 0
            seats_saved = 0
            opt_status = f"Error: {exc}"
            opt_assignments = []
            opt_unit_allocations = {}

        results.append({
            "idx": idx,
            # Parameters
            "alloc_pct": effective_alloc,
            "rto_mandate": rto,
            "cap_red": cap_red,
            "objective": objective,
            # Simulation metrics
            "demand": demand,
            "capacity": capacity,
            "headroom": headroom,
            "total_gap": total_gap,
            "units_at_risk": units_at_risk,
            "avg_fragmentation": round(avg_frag, 3),
            # Optimizer metrics
            "opt_seats": opt_seats,
            "floors_used": floors_used,
            "seats_saved": seats_saved,
            "opt_status": opt_status,
            # For adoption
            "_assignments": opt_assignments,
            "_unit_allocations": opt_unit_allocations,
            "_temp_scenario": temp,
            "_rc": rc,
        })

    return results


def _error_result(idx, alloc, rto, cap_red, objective, error_msg) -> dict:
    return {
        "idx": idx,
        "alloc_pct": alloc, "rto_mandate": rto, "cap_red": cap_red, "objective": objective,
        "demand": 0, "capacity": 0, "headroom": 0, "total_gap": 0,
        "units_at_risk": 0, "avg_fragmentation": 0,
        "opt_seats": 0, "floors_used": 0, "seats_saved": 0,
        "opt_status": f"Error: {error_msg}",
        "_assignments": [], "_unit_allocations": {}, "_temp_scenario": None, "_rc": {},
    }


def rank_scenarios(results: List[dict]) -> List[dict]:
    """Score and rank scenarios by composite metric (higher = better).

    Scoring components (each normalized 0-1):
    - headroom_score:      positive headroom normalized (penalize shortfall)
    - gap_score:           no shortfall = full score; negative = proportional penalty
    - fragmentation_score: lower avg fragmentation = higher score
    - consolidation_score: fewer floors used = higher score
    """
    # Filter out error results
    valid = [r for r in results if not r["opt_status"].startswith("Error")]
    if not valid:
        ranked = [dict(r, rank=i + 1, composite_score=0.0, score_breakdown={}) for i, r in enumerate(results)]
        return ranked

    # Compute ranges for normalization
    headrooms      = [r["headroom"] for r in valid]
    gaps           = [r["total_gap"] for r in valid]
    frags          = [r["avg_fragmentation"] for r in valid]
    floors         = [r["floors_used"] for r in valid]

    max_headroom   = max(headrooms) if max(headrooms) != min(headrooms) else 1
    min_headroom   = min(headrooms)
    max_frag       = max(frags) if max(frags) != min(frags) else 1
    max_floors_val = max(floors) if max(floors) != min(floors) else 1

    def score(r):
        # Headroom: higher is better, but normalize relative to range
        h_range = max_headroom - min_headroom or 1
        h_score = max(0.0, (r["headroom"] - min_headroom) / h_range)

        # Gap: 0 or positive → full score; negative → penalty
        g_score = 1.0 if r["total_gap"] >= 0 else max(0.0, 1.0 + r["total_gap"] / max(1, abs(min(gaps))))

        # Fragmentation: lower = better
        f_score = 1.0 - (r["avg_fragmentation"] / max_frag) if max_frag > 0 else 1.0

        # Floors: fewer = better
        fl_score = 1.0 - (r["floors_used"] / max_floors_val) if max_floors_val > 0 else 1.0

        composite = 0.35 * h_score + 0.35 * g_score + 0.15 * f_score + 0.15 * fl_score
        return composite, {
            "headroom": round(h_score, 3),
            "gap": round(g_score, 3),
            "fragmentation": round(f_score, 3),
            "consolidation": round(fl_score, 3),
        }

    scored = []
    for r in results:
        if r["opt_status"].startswith("Error"):
            scored.append(dict(r, composite_score=0.0, rank=999, score_breakdown={}))
        else:
            composite, breakdown = score(r)
            scored.append(dict(r, composite_score=round(composite, 4), score_breakdown=breakdown))

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    for rank_pos, item in enumerate(scored):
        item["rank"] = rank_pos + 1

    return scored


def get_best_scenario(ranked_results: List[dict]) -> Optional[dict]:
    """Return the top-ranked (rank=1) scenario, or None if empty."""
    if not ranked_results:
        return None
    return min(ranked_results, key=lambda r: r["rank"])


def build_explanation(best: dict) -> str:
    """Build a human-readable explanation of why this scenario ranked best."""
    parts = []
    bd = best.get("score_breakdown", {})
    if bd.get("gap", 0) >= 0.95:
        parts.append(f"no seat shortfall (total gap: {best['total_gap']:+,})")
    if bd.get("headroom", 0) >= 0.7:
        parts.append(f"strong capacity headroom ({best['headroom']:+,} seats)")
    if bd.get("fragmentation", 0) >= 0.7:
        parts.append(f"low fragmentation ({best['avg_fragmentation']:.2f})")
    if bd.get("consolidation", 0) >= 0.7:
        parts.append(f"consolidated placement ({best['floors_used']} floors)")
    if not parts:
        parts.append(f"best composite score ({best['composite_score']:.2f})")
    return "; ".join(parts).capitalize() + "."
