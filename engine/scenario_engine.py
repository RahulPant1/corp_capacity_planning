"""Scenario simulation engine — clone baseline, apply overrides, recompute."""

import copy
from typing import Dict, List, Optional
from models.unit import Unit
from models.attendance import AttendanceProfile
from models.building import Floor
from models.scenario import Scenario, ScenarioOverride
from models.allocation import AllocationRecommendation, FloorAssignment
from engine.allocation_engine import run_allocation
from engine.spatial import assign_units_to_floors


def apply_overrides(
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    scenario: Scenario,
) -> tuple[List[Unit], Dict[str, AttendanceProfile]]:
    """Apply scenario overrides to units and attendance, returning modified copies."""
    modified_units = []
    modified_attendance = dict(attendance_map)

    for unit in units:
        u = copy.deepcopy(unit)
        override = scenario.unit_overrides.get(u.unit_name)
        if override:
            if override.hc_growth_pct is not None:
                u.hc_growth_pct = override.hc_growth_pct
            if override.attrition_pct is not None:
                u.attrition_pct = override.attrition_pct
        modified_units.append(u)

    for unit_name, override in scenario.unit_overrides.items():
        if unit_name in modified_attendance:
            att = copy.deepcopy(modified_attendance[unit_name])
            if override.median_hc is not None:
                att.monthly_median_hc = override.median_hc
            if override.max_hc is not None:
                att.monthly_max_hc = override.max_hc
            if override.avg_rto_days is not None:
                att.avg_rto_days_per_week = override.avg_rto_days
            modified_attendance[unit_name] = att

    # Apply global RTO mandate if set
    if scenario.params.global_rto_mandate_days is not None:
        for name, att in modified_attendance.items():
            att = copy.deepcopy(att)
            att.avg_rto_days_per_week = max(att.avg_rto_days_per_week,
                                             scenario.params.global_rto_mandate_days)
            modified_attendance[name] = att

    return modified_units, modified_attendance


def apply_floor_modifications(
    floors: List[Floor],
    scenario: Scenario,
) -> List[Floor]:
    """Apply scenario floor modifications (exclusions, capacity reduction)."""
    excluded = set(scenario.params.excluded_floors)
    reduction = scenario.params.capacity_reduction_pct

    modified = []
    for f in floors:
        if f.floor_id in excluded:
            continue
        f_copy = copy.deepcopy(f)
        if reduction > 0:
            f_copy.total_seats = max(0, round(f_copy.total_seats * (1 - reduction)))
        modified.append(f_copy)
    return modified


def run_scenario(
    scenario: Scenario,
    base_units: List[Unit],
    base_attendance_map: Dict[str, AttendanceProfile],
    base_floors: List[Floor],
    rule_config: Optional[dict] = None,
) -> Scenario:
    """Run a full scenario simulation and populate results on the scenario."""
    # Apply overrides
    units, attendance_map = apply_overrides(base_units, base_attendance_map, scenario)
    floors = apply_floor_modifications(base_floors, scenario)

    # Apply allocation % overrides after computing recommendations
    allocations = run_allocation(
        units, attendance_map, floors,
        scenario.planning_horizon_months, rule_config,
    )

    # Apply manual allocation % overrides
    for alloc in allocations:
        override = scenario.unit_overrides.get(alloc.unit_name)
        if override and override.alloc_pct_override is not None:
            alloc.is_overridden = True
            alloc.override_alloc_pct = override.alloc_pct_override
            alloc.recommended_alloc_pct = override.alloc_pct_override
            unit = next((u for u in units if u.unit_name == alloc.unit_name), None)
            if unit:
                alloc.effective_demand_seats = round(override.alloc_pct_override * unit.current_total_hc)

    # Re-distribute after overrides
    total_supply = sum(f.total_seats for f in floors)
    from engine.allocation_engine import distribute_seats
    allocations = distribute_seats(allocations, units, total_supply, rule_config)

    # Assign to floors
    excluded_ids = list(set(scenario.params.excluded_floors))
    assignments, frag_scores = assign_units_to_floors(allocations, floors, excluded_ids)

    # Store results
    scenario.allocation_results = allocations
    scenario.floor_assignments = assignments

    return scenario


def compare_scenarios(
    scenario_a: Scenario,
    scenario_b: Scenario,
) -> List[dict]:
    """Compare two scenarios and return per-unit differences."""
    a_map = {r.unit_name: r for r in scenario_a.allocation_results}
    b_map = {r.unit_name: r for r in scenario_b.allocation_results}

    all_units = sorted(set(list(a_map.keys()) + list(b_map.keys())))
    diffs = []
    for unit_name in all_units:
        a = a_map.get(unit_name)
        b = b_map.get(unit_name)
        diffs.append({
            "Unit": unit_name,
            f"{scenario_a.name} Alloc%": f"{a.recommended_alloc_pct:.1%}" if a else "N/A",
            f"{scenario_b.name} Alloc%": f"{b.recommended_alloc_pct:.1%}" if b else "N/A",
            f"{scenario_a.name} Seats": a.allocated_seats if a else 0,
            f"{scenario_b.name} Seats": b.allocated_seats if b else 0,
            "Seat Change": (b.allocated_seats if b else 0) - (a.allocated_seats if a else 0),
            f"{scenario_a.name} Gap": a.seat_gap if a else 0,
            f"{scenario_b.name} Gap": b.seat_gap if b else 0,
        })
    return diffs
