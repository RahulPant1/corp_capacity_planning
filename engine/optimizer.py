"""PuLP LP-based seat allocation optimizer."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pulp

from models.building import Floor
from models.unit import Unit
from models.allocation import AllocationRecommendation, FloorAssignment


@dataclass
class OptimizationResult:
    status: str  # "Optimal", "Infeasible", "Not Solved"
    objective_value: float
    assignments: List[FloorAssignment]
    unit_allocations: Dict[str, int]  # unit_name -> total seats
    before_after: List[dict]  # comparison data
    consolidation_suggestions: List[str]
    message: str = ""


def _build_adjacency_weights(
    floors: List[Floor],
    baseline_assignments: List[FloorAssignment],
) -> Dict[Tuple[str, str], float]:
    """Build adjacency bonus weights for unit-floor pairs."""
    weights = {}
    # Map existing unit -> set of (tower_id, floor_number)
    unit_floors = {}
    for a in baseline_assignments:
        if a.unit_name not in unit_floors:
            unit_floors[a.unit_name] = set()
        unit_floors[a.unit_name].add((a.tower_id, a.floor_number))

    for f in floors:
        for unit_name, existing in unit_floors.items():
            bonus = 0
            if (f.tower_id, f.floor_number) in existing:
                bonus = 100
            elif any(t == f.tower_id and abs(fn - f.floor_number) == 1
                     for t, fn in existing):
                bonus = 60
            elif any(t == f.tower_id for t, _ in existing):
                bonus = 30
            weights[(unit_name, f.floor_id)] = bonus

    return weights


def optimize_allocation(
    allocations: List[AllocationRecommendation],
    floors: List[Floor],
    baseline_assignments: List[FloorAssignment],
    objective: str = "min_shortfall",
    excluded_floor_ids: List[str] = None,
    min_alloc_pct: float = 0.20,
    max_alloc_pct: float = 1.50,
    units: Optional[List[Unit]] = None,
) -> OptimizationResult:
    """
    Run LP optimization for seat allocation.

    Objectives:
    - min_shortfall: Minimize total seat shortfall
    - max_cohesion: Maximize floor cohesion (adjacency bonuses)
    - min_floors: Minimize number of floors used
    - fair_allocation: Minimize worst-case shortfall ratio
    """
    excluded = set(excluded_floor_ids or [])
    available_floors = [f for f in floors if f.floor_id not in excluded]

    unit_names = [a.unit_name for a in allocations]
    floor_ids = [f.floor_id for f in available_floors]
    floor_map = {f.floor_id: f for f in available_floors}
    alloc_map = {a.unit_name: a for a in allocations}
    unit_map = {u.unit_name: u for u in (units or [])}

    prob = pulp.LpProblem("SeatAllocation", pulp.LpMinimize)

    # Decision variables: x[unit][floor] = seats assigned
    x = {}
    for u in unit_names:
        for fid in floor_ids:
            x[(u, fid)] = pulp.LpVariable(
                f"x_{u}_{fid}", lowBound=0,
                upBound=floor_map[fid].total_seats, cat="Integer",
            )

    # Binary variables for floor usage (needed for min_floors)
    y = {}
    if objective == "min_floors":
        for u in unit_names:
            for fid in floor_ids:
                y[(u, fid)] = pulp.LpVariable(f"y_{u}_{fid}", cat="Binary")

    # --- Objective ---
    if objective == "min_shortfall":
        # Slack variables for shortfall
        s = {}
        for u in unit_names:
            s[u] = pulp.LpVariable(f"s_{u}", lowBound=0)
            prob += s[u] >= alloc_map[u].effective_demand_seats - pulp.lpSum(
                x[(u, fid)] for fid in floor_ids
            ), f"shortfall_{u}"
        prob += pulp.lpSum(s[u] for u in unit_names), "total_shortfall"

    elif objective == "max_cohesion":
        weights = _build_adjacency_weights(available_floors, baseline_assignments)
        prob += -pulp.lpSum(
            x[(u, fid)] * weights.get((u, fid), 0)
            for u in unit_names for fid in floor_ids
        ), "neg_cohesion"

    elif objective == "min_floors":
        for u in unit_names:
            for fid in floor_ids:
                prob += x[(u, fid)] <= floor_map[fid].total_seats * y[(u, fid)], f"link_{u}_{fid}"
        prob += pulp.lpSum(y[(u, fid)] for u in unit_names for fid in floor_ids), "total_floors"

    elif objective == "fair_allocation":
        z = pulp.LpVariable("z_fairness", lowBound=0)
        for u in unit_names:
            demand = alloc_map[u].effective_demand_seats
            if demand > 0:
                prob += z >= (demand - pulp.lpSum(
                    x[(u, fid)] for fid in floor_ids
                )) / demand, f"fairness_{u}"
        prob += z, "max_shortfall_ratio"

    # --- Constraints ---
    # C1: Floor capacity
    for fid in floor_ids:
        prob += pulp.lpSum(x[(u, fid)] for u in unit_names) <= floor_map[fid].total_seats, f"cap_{fid}"

    # C2: Min allocation (soft — relax if infeasible)
    for u in unit_names:
        unit = unit_map.get(u)
        if unit:
            min_seats = max(0, round(min_alloc_pct * unit.current_total_hc))
            prob += pulp.lpSum(x[(u, fid)] for fid in floor_ids) >= min_seats, f"min_{u}"

    # C3: Max allocation
    for u in unit_names:
        unit = unit_map.get(u)
        if unit:
            max_seats = round(max_alloc_pct * unit.current_total_hc)
            prob += pulp.lpSum(x[(u, fid)] for fid in floor_ids) <= max_seats, f"max_{u}"

    # --- Solve ---
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))

    status = pulp.LpStatus[prob.status]

    if status != "Optimal":
        # Try relaxing min allocation constraints
        for u in unit_names:
            constraint_name = f"min_{u}"
            if constraint_name in prob.constraints:
                del prob.constraints[constraint_name]

        prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
        status = pulp.LpStatus[prob.status]
        if status == "Optimal":
            status = "Optimal (relaxed min allocation)"

    if status not in ("Optimal", "Optimal (relaxed min allocation)"):
        return OptimizationResult(
            status=status,
            objective_value=0,
            assignments=[],
            unit_allocations={},
            before_after=[],
            consolidation_suggestions=[],
            message=f"Optimization could not find a solution. Status: {status}",
        )

    # --- Extract results ---
    new_assignments = []
    unit_totals = {u: 0 for u in unit_names}

    for u in unit_names:
        for fid in floor_ids:
            val = int(round(x[(u, fid)].varValue or 0))
            if val > 0:
                f = floor_map[fid]
                new_assignments.append(FloorAssignment(
                    unit_name=u,
                    building_id=f.building_id,
                    tower_id=f.tower_id,
                    floor_number=f.floor_number,
                    seats_assigned=val,
                    adjacency_tier="optimized",
                ))
                unit_totals[u] += val

    # Before/After comparison
    old_totals = {}
    for a in baseline_assignments:
        old_totals[a.unit_name] = old_totals.get(a.unit_name, 0) + a.seats_assigned

    old_floor_count = {}
    for a in baseline_assignments:
        key = a.unit_name
        if key not in old_floor_count:
            old_floor_count[key] = set()
        old_floor_count[key].add((a.tower_id, a.floor_number))

    new_floor_count = {}
    for a in new_assignments:
        key = a.unit_name
        if key not in new_floor_count:
            new_floor_count[key] = set()
        new_floor_count[key].add((a.tower_id, a.floor_number))

    before_after = []
    for u in unit_names:
        before_seats = old_totals.get(u, 0)
        after_seats = unit_totals.get(u, 0)
        before_floors = len(old_floor_count.get(u, set()))
        after_floors = len(new_floor_count.get(u, set()))
        before_after.append({
            "Unit": u,
            "Before Seats": before_seats,
            "After Seats": after_seats,
            "Seat Change": after_seats - before_seats,
            "Before Floors": before_floors,
            "After Floors": after_floors,
            "Floor Change": after_floors - before_floors,
        })

    # Consolidation suggestions
    suggestions = []
    for u in unit_names:
        old_f = len(old_floor_count.get(u, set()))
        new_f = len(new_floor_count.get(u, set()))
        if new_f < old_f:
            suggestions.append(
                f"{u}: Consolidated from {old_f} floors to {new_f} floors"
            )

    return OptimizationResult(
        status=status,
        objective_value=pulp.value(prob.objective) or 0,
        assignments=new_assignments,
        unit_allocations=unit_totals,
        before_after=before_after,
        consolidation_suggestions=suggestions,
        message=f"Optimization complete. Objective ({objective}): {pulp.value(prob.objective):.2f}",
    )
