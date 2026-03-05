"""What-If Sensitivity Analysis — auto-vary constraints, measure seat gap impact."""

import copy
from typing import Dict, List, Optional
from collections import defaultdict

from models.unit import Unit
from models.attendance import AttendanceProfile
from models.building import Floor
from models.scenario import Scenario
from engine.scenario_engine import run_scenario
from config.defaults import (
    SENSITIVITY_ALLOC_VARIATIONS,
    SENSITIVITY_HORIZON_VARIATIONS,
    SENSITIVITY_CAPACITY_REDUCTIONS,
    SENSITIVITY_RTO_VARIATIONS,
)


def _compute_total_gap(scenario: Scenario) -> int:
    """Sum of seat_gap across all allocation results."""
    return sum(a.seat_gap for a in scenario.allocation_results)


def run_sensitivity_analysis(
    base_scenario: Scenario,
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    floors: List[Floor],
    rule_config: Optional[dict] = None,
) -> List[dict]:
    """Vary key parameters one at a time and measure impact on total seat gap.

    Returns list of dicts sorted by absolute impact descending:
        parameter, variation_label, variation_value,
        baseline_gap, result_gap, gap_delta, abs_delta
    """
    results = []
    cfg = rule_config or {}

    # Baseline gap
    baseline = copy.deepcopy(base_scenario)
    baseline = run_scenario(baseline, units, attendance_map, floors, cfg)
    baseline_gap = _compute_total_gap(baseline)

    # 1. Vary global_alloc_pct
    base_alloc = cfg.get("global_alloc_pct", 0.80)
    for delta in SENSITIVITY_ALLOC_VARIATIONS:
        new_alloc = max(0.10, min(1.50, base_alloc + delta))
        test_cfg = dict(cfg)
        test_cfg["global_alloc_pct"] = new_alloc
        test_scenario = copy.deepcopy(base_scenario)
        test_scenario = run_scenario(test_scenario, units, attendance_map, floors, test_cfg)
        result_gap = _compute_total_gap(test_scenario)
        results.append({
            "parameter": "Global Alloc %",
            "variation_label": f"{delta:+.0%}",
            "variation_value": new_alloc,
            "baseline_gap": baseline_gap,
            "result_gap": result_gap,
            "gap_delta": result_gap - baseline_gap,
            "abs_delta": abs(result_gap - baseline_gap),
        })

    # 2. Vary planning horizon
    base_horizon = base_scenario.planning_horizon_months
    for delta in SENSITIVITY_HORIZON_VARIATIONS:
        new_horizon = max(1, base_horizon + delta)
        test_scenario = copy.deepcopy(base_scenario)
        test_scenario.planning_horizon_months = new_horizon
        test_scenario = run_scenario(test_scenario, units, attendance_map, floors, cfg)
        result_gap = _compute_total_gap(test_scenario)
        results.append({
            "parameter": "Planning Horizon",
            "variation_label": f"{delta:+d} months",
            "variation_value": new_horizon,
            "baseline_gap": baseline_gap,
            "result_gap": result_gap,
            "gap_delta": result_gap - baseline_gap,
            "abs_delta": abs(result_gap - baseline_gap),
        })

    # 3. Vary capacity reduction
    for cap_red in SENSITIVITY_CAPACITY_REDUCTIONS:
        test_scenario = copy.deepcopy(base_scenario)
        test_scenario.params.capacity_reduction_pct = cap_red
        test_scenario = run_scenario(test_scenario, units, attendance_map, floors, cfg)
        result_gap = _compute_total_gap(test_scenario)
        results.append({
            "parameter": "Capacity Reduction",
            "variation_label": f"{cap_red:.0%}",
            "variation_value": cap_red,
            "baseline_gap": baseline_gap,
            "result_gap": result_gap,
            "gap_delta": result_gap - baseline_gap,
            "abs_delta": abs(result_gap - baseline_gap),
        })

    # 4. Vary global RTO mandate
    base_rto = base_scenario.params.global_rto_mandate_days or 3.0
    for delta in SENSITIVITY_RTO_VARIATIONS:
        new_rto = max(0.5, min(5.0, base_rto + delta))
        test_scenario = copy.deepcopy(base_scenario)
        test_scenario.params.global_rto_mandate_days = new_rto
        test_scenario = run_scenario(test_scenario, units, attendance_map, floors, cfg)
        result_gap = _compute_total_gap(test_scenario)
        results.append({
            "parameter": "RTO Mandate",
            "variation_label": f"{delta:+.1f} days",
            "variation_value": new_rto,
            "baseline_gap": baseline_gap,
            "result_gap": result_gap,
            "gap_delta": result_gap - baseline_gap,
            "abs_delta": abs(result_gap - baseline_gap),
        })

    results.sort(key=lambda r: r["abs_delta"], reverse=True)
    return results


def get_parameter_impact_summary(results: List[dict]) -> List[dict]:
    """Aggregate sensitivity results by parameter to rank which lever matters most."""
    by_param = defaultdict(list)
    for r in results:
        by_param[r["parameter"]].append(r)

    summary = []
    for param, entries in by_param.items():
        deltas = [e["gap_delta"] for e in entries]
        max_pos = max(deltas) if deltas else 0
        max_neg = min(deltas) if deltas else 0
        impact_range = max_pos - max_neg
        most_impactful = max(entries, key=lambda e: e["abs_delta"])
        summary.append({
            "parameter": param,
            "max_positive_delta": max_pos,
            "max_negative_delta": max_neg,
            "range": impact_range,
            "most_impactful_variation": most_impactful["variation_label"],
        })

    summary.sort(key=lambda s: s["range"], reverse=True)
    return summary


def run_single_what_if(
    base_scenario: Scenario,
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    floors: List[Floor],
    rule_config: Optional[dict] = None,
    alloc_pct: Optional[float] = None,
    horizon_months: Optional[int] = None,
    capacity_reduction: Optional[float] = None,
    rto_mandate: Optional[float] = None,
) -> dict:
    """Run a single what-if comparison with user-specified parameter overrides.

    Each parameter defaults to the base scenario value when not specified.
    Returns: {baseline_gap, result_gap, gap_delta, changed_params}
    """
    cfg = dict(rule_config or {})
    if alloc_pct is not None:
        cfg["global_alloc_pct"] = alloc_pct

    test = copy.deepcopy(base_scenario)
    if horizon_months is not None:
        test.planning_horizon_months = horizon_months
    if capacity_reduction is not None:
        test.params.capacity_reduction_pct = capacity_reduction
    if rto_mandate is not None:
        test.params.global_rto_mandate_days = rto_mandate

    baseline = copy.deepcopy(base_scenario)
    baseline = run_scenario(baseline, units, attendance_map, floors, rule_config or {})
    baseline_gap = _compute_total_gap(baseline)

    test = run_scenario(test, units, attendance_map, floors, cfg)
    result_gap = _compute_total_gap(test)

    changed = {
        k: v for k, v in {
            "Global Alloc %": alloc_pct,
            "Planning Horizon": horizon_months,
            "Capacity Reduction": capacity_reduction,
            "RTO Mandate": rto_mandate,
        }.items() if v is not None
    }

    return {
        "baseline_gap": baseline_gap,
        "result_gap": result_gap,
        "gap_delta": result_gap - baseline_gap,
        "changed_params": changed,
    }
