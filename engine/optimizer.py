"""PuLP LP-based seat allocation optimizer."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pulp

from models.building import Floor
from models.unit import Unit
from models.allocation import AllocationRecommendation, FloorAssignment
from models.attendance import AttendanceProfile
from config.defaults import PEAK_BUFFER_MULTIPLIER, WORKING_DAYS_PER_WEEK


@dataclass
class OptimizationResult:
    status: str  # "Optimal", "Infeasible", "Not Solved"
    objective_value: float
    assignments: List[FloorAssignment]
    unit_allocations: Dict[str, int]  # unit_name -> total seats
    before_after: List[dict]  # comparison data
    consolidation_suggestions: List[str]
    message: str = ""
    savings_summary: Optional[dict] = None  # for RTO objectives


def _build_adjacency_weights(
    floors: List[Floor],
    baseline_assignments: List[FloorAssignment],
) -> Dict[Tuple[str, str], float]:
    """Build adjacency bonus weights for unit-floor pairs.

    Hierarchy: same_floor (100) > adjacent_floor (60) > same_tower (30) >
    same_building (15) > cross_building (0).
    """
    weights = {}
    unit_floors = {}
    for a in baseline_assignments:
        if a.unit_name not in unit_floors:
            unit_floors[a.unit_name] = set()
        unit_floors[a.unit_name].add((a.building_id, a.tower_id, a.floor_number))

    for f in floors:
        for unit_name, existing in unit_floors.items():
            bonus = 0
            if (f.building_id, f.tower_id, f.floor_number) in existing:
                bonus = 100
            elif any(t == f.tower_id and abs(fn - f.floor_number) == 1
                     for _, t, fn in existing):
                bonus = 60
            elif any(t == f.tower_id for _, t, _ in existing):
                bonus = 30
            elif any(b == f.building_id for b, _, _ in existing):
                bonus = 15
            weights[(unit_name, f.floor_id)] = bonus

    return weights


def _compute_rto_demand(att: AttendanceProfile, buffer_mult: float, override_rto: float = None) -> int:
    """Compute attendance-based seat need for a unit."""
    rto = override_rto if override_rto is not None else att.avg_rto_days_per_week
    base = att.monthly_median_hc
    peak = (att.monthly_max_hc - att.monthly_median_hc) * buffer_mult
    return max(1, round((base + peak) * (rto / WORKING_DAYS_PER_WEEK)))


def optimize_allocation(
    allocations: List[AllocationRecommendation],
    floors: List[Floor],
    baseline_assignments: List[FloorAssignment],
    objective: str = "optimal_placement",
    excluded_floor_ids: List[str] = None,
    units: Optional[List[Unit]] = None,
    attendance_map: Optional[Dict[str, AttendanceProfile]] = None,
    rule_config: Optional[dict] = None,
    target_rto_days: Optional[float] = None,
    # Runtime constraints
    max_floors_per_unit: Optional[int] = None,
    pinned_tower_ids: Optional[Dict[str, List[str]]] = None,
    min_guarantee_pct: Optional[float] = None,
) -> OptimizationResult:
    """
    Run LP optimization for seat allocation.

    Objectives:
    - optimal_placement: Place units per allocation rule on fewest floors with max cohesion
    - rto_based: Allocate by actual attendance patterns, free unused capacity
    - rto_whatif: Simulate a different RTO policy (target_rto_days)

    Runtime constraints:
    - max_floors_per_unit: each unit uses at most this many floors
    - pinned_tower_ids: {unit_name: [tower_id, ...]} — restrict units to specific towers
    - min_guarantee_pct: each unit receives at least this fraction of its demand
    """
    cfg = rule_config or {}
    buffer_mult = cfg.get("peak_buffer_multiplier", PEAK_BUFFER_MULTIPLIER)

    excluded = set(excluded_floor_ids or [])
    available_floors = [f for f in floors if f.floor_id not in excluded]

    unit_names = [a.unit_name for a in allocations]
    floor_ids = [f.floor_id for f in available_floors]
    floor_map = {f.floor_id: f for f in available_floors}
    alloc_map = {a.unit_name: a for a in allocations}
    unit_map = {u.unit_name: u for u in (units or [])}
    att_map = attendance_map or {}

    # Determine demand per unit based on objective
    demand = {}
    for u in unit_names:
        if objective == "rto_based" and u in att_map:
            demand[u] = _compute_rto_demand(att_map[u], buffer_mult)
        elif objective == "rto_whatif" and u in att_map and target_rto_days is not None:
            demand[u] = _compute_rto_demand(att_map[u], buffer_mult, override_rto=target_rto_days)
        else:
            demand[u] = alloc_map[u].effective_demand_seats

    prob = pulp.LpProblem("SeatAllocation", pulp.LpMinimize)

    # Decision variables: x[unit][floor] = seats assigned
    x = {}
    for u in unit_names:
        for fid in floor_ids:
            x[(u, fid)] = pulp.LpVariable(
                f"x_{u}_{fid}", lowBound=0,
                upBound=floor_map[fid].total_seats, cat="Integer",
            )

    # Binary variables for floor usage (used by all objectives for min-floors)
    y = {}
    for u in unit_names:
        for fid in floor_ids:
            y[(u, fid)] = pulp.LpVariable(f"y_{u}_{fid}", cat="Binary")
            # Link: if x > 0 then y = 1
            prob += x[(u, fid)] <= floor_map[fid].total_seats * y[(u, fid)], f"link_{u}_{fid}"

    # Adjacency weights (cohesion tiebreaker)
    weights = _build_adjacency_weights(available_floors, baseline_assignments)
    cohesion_term = pulp.lpSum(
        x[(u, fid)] * weights.get((u, fid), 0)
        for u in unit_names for fid in floor_ids
    )
    COHESION_WEIGHT = 0.001
    FLOOR_WEIGHT = 1.0

    # Objective: minimize floors used + cohesion tiebreaker (all objectives share this)
    # Shortfall slack for when demand exceeds capacity
    s = {}
    for u in unit_names:
        s[u] = pulp.LpVariable(f"s_{u}", lowBound=0)
        prob += s[u] >= demand[u] - pulp.lpSum(
            x[(u, fid)] for fid in floor_ids
        ), f"shortfall_{u}"

    SHORTFALL_WEIGHT = 100.0  # High priority: meet demand first
    prob += (
        SHORTFALL_WEIGHT * pulp.lpSum(s[u] for u in unit_names)
        + FLOOR_WEIGHT * pulp.lpSum(y[(u, fid)] for u in unit_names for fid in floor_ids)
        - COHESION_WEIGHT * cohesion_term
    ), "combined_objective"

    # --- Constraints ---
    # C1: Floor capacity
    for fid in floor_ids:
        prob += pulp.lpSum(x[(u, fid)] for u in unit_names) <= floor_map[fid].total_seats, f"cap_{fid}"

    # C2: Cap at demand (each unit gets at most what they need)
    for u in unit_names:
        prob += pulp.lpSum(x[(u, fid)] for fid in floor_ids) <= demand[u], f"max_{u}"

    # C3: Max floors per unit (runtime constraint)
    if max_floors_per_unit is not None:
        for u in unit_names:
            prob += pulp.lpSum(y[(u, fid)] for fid in floor_ids) <= max_floors_per_unit, f"maxfloors_{u}"

    # C4: Pin units to specific towers (zero out disallowed floor vars)
    if pinned_tower_ids:
        for u, allowed_towers in pinned_tower_ids.items():
            if u in unit_names and allowed_towers:
                for fid in floor_ids:
                    if floor_map[fid].tower_id not in allowed_towers:
                        x[(u, fid)].upBound = 0

    # C5: Minimum seats guarantee per unit
    guaranteed_units = []
    if min_guarantee_pct is not None and min_guarantee_pct > 0:
        for u in unit_names:
            min_seats = round(min_guarantee_pct * demand[u])
            if min_seats > 0:
                prob += pulp.lpSum(x[(u, fid)] for fid in floor_ids) >= min_seats, f"minguarantee_{u}"
                guaranteed_units.append(u)

    # --- Solve ---
    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
    status = pulp.LpStatus[prob.status]
    relaxed_guarantee = False

    if status != "Optimal" and guaranteed_units:
        # Relax min guarantee constraints and retry
        for u in guaranteed_units:
            cname = f"minguarantee_{u}"
            if cname in prob.constraints:
                del prob.constraints[cname]
        prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
        status = pulp.LpStatus[prob.status]
        relaxed_guarantee = True

    if status != "Optimal":
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
        if a.unit_name not in old_floor_count:
            old_floor_count[a.unit_name] = set()
        old_floor_count[a.unit_name].add((a.tower_id, a.floor_number))

    new_floor_count = {}
    for a in new_assignments:
        if a.unit_name not in new_floor_count:
            new_floor_count[a.unit_name] = set()
        new_floor_count[a.unit_name].add((a.tower_id, a.floor_number))

    before_after = []
    for u in unit_names:
        before_seats = old_totals.get(u, 0)
        after_seats = unit_totals.get(u, 0)
        before_floors = len(old_floor_count.get(u, set()))
        after_floors = len(new_floor_count.get(u, set()))
        before_after.append({
            "Unit": u,
            "Demand": demand[u],
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

    # Savings summary (for RTO objectives)
    savings = None
    if objective in ("rto_based", "rto_whatif"):
        alloc_total = sum(alloc_map[u].effective_demand_seats for u in unit_names)
        rto_total = sum(demand[u] for u in unit_names)
        optimized_total = sum(unit_totals.values())

        all_old_floors = set()
        for a in baseline_assignments:
            all_old_floors.add((a.tower_id, a.floor_number))
        all_new_floors = set()
        for a in new_assignments:
            all_new_floors.add((a.tower_id, a.floor_number))

        savings = {
            "allocation_rule_seats": alloc_total,
            "rto_based_seats": rto_total,
            "optimized_seats": optimized_total,
            "seats_saved": alloc_total - optimized_total,
            "floors_before": len(all_old_floors),
            "floors_after": len(all_new_floors),
            "floors_freed": len(all_old_floors) - len(all_new_floors),
        }

    obj_label = {
        "optimal_placement": "Optimal Placement",
        "rto_based": "RTO-Based",
        "rto_whatif": f"What-If RTO ({target_rto_days} days)" if target_rto_days else "What-If RTO",
    }.get(objective, objective)

    msg = f"Optimization complete ({obj_label}). Total seats: {sum(unit_totals.values()):,}."
    if relaxed_guarantee:
        msg += " Note: minimum seats guarantee was relaxed due to capacity constraints."

    return OptimizationResult(
        status=status,
        objective_value=pulp.value(prob.objective) or 0,
        assignments=new_assignments,
        unit_allocations=unit_totals,
        before_after=before_after,
        consolidation_suggestions=suggestions,
        message=msg,
        savings_summary=savings,
    )
