"""Rule-based allocation logic — the core business engine."""

from typing import Dict, List, Optional, Tuple
from models.unit import Unit
from models.attendance import AttendanceProfile
from models.allocation import AllocationRecommendation
from models.building import Floor
from engine.explainer import explain_allocation, explain_simple_allocation
from config.defaults import (
    MIN_ALLOC_PCT, MAX_ALLOC_PCT,
    PEAK_BUFFER_MULTIPLIER, SHRINK_CONTRIBUTION_FACTOR,
    PRIORITY_ORDER, WORKING_DAYS_PER_WEEK,
    ALLOCATION_MODE, DEFAULT_GLOBAL_ALLOC_PCT,
)


def compute_recommended_allocation(
    unit: Unit,
    attendance: AttendanceProfile,
    horizon_months: int,
    rule_config: Optional[dict] = None,
) -> AllocationRecommendation:
    """Derive recommended allocation % and effective demand for a single unit."""
    cfg = rule_config or {}
    min_alloc = cfg.get("min_alloc_pct", MIN_ALLOC_PCT)
    max_alloc = cfg.get("max_alloc_pct", MAX_ALLOC_PCT)
    buffer_multiplier = cfg.get("peak_buffer_multiplier", PEAK_BUFFER_MULTIPLIER)

    hc = unit.current_total_hc
    if hc == 0:
        return AllocationRecommendation(
            unit_name=unit.unit_name,
            recommended_alloc_pct=0,
            effective_demand_seats=0,
            allocated_seats=0,
            seat_gap=0,
            fragmentation_score=0,
            explanation_steps=["Unit has 0 headcount — no allocation needed."],
        )

    # Step 1: Base demand ratio
    base_ratio = attendance.monthly_median_hc / hc

    # Step 2: Peak buffer
    peak_buffer = (attendance.monthly_max_hc - attendance.monthly_median_hc) / hc
    peak_buffer *= buffer_multiplier

    # Step 3: RTO scaling (scale base, not peak buffer)
    rto_factor = attendance.avg_rto_days_per_week / WORKING_DAYS_PER_WEEK
    scaled_ratio = base_ratio * rto_factor

    # Step 4: Growth/attrition projection
    net_change = unit.hc_growth_pct - unit.attrition_pct
    horizon_factor = 1 + (net_change * (horizon_months / 12))
    growth_adjusted = scaled_ratio * horizon_factor

    # Step 5: Combine
    raw_alloc_pct = growth_adjusted + peak_buffer
    was_clamped = raw_alloc_pct < min_alloc or raw_alloc_pct > max_alloc
    recommended_alloc_pct = max(min_alloc, min(max_alloc, raw_alloc_pct))

    # Step 6: Effective demand
    effective_demand = round(recommended_alloc_pct * hc)

    explanation = explain_allocation(
        unit_name=unit.unit_name,
        current_hc=hc,
        monthly_median_hc=attendance.monthly_median_hc,
        monthly_max_hc=attendance.monthly_max_hc,
        avg_rto_days=attendance.avg_rto_days_per_week,
        hc_growth_pct=unit.hc_growth_pct,
        attrition_pct=unit.attrition_pct,
        horizon_months=horizon_months,
        base_ratio=base_ratio,
        peak_buffer=peak_buffer,
        rto_factor=rto_factor,
        scaled_ratio=scaled_ratio,
        horizon_factor=horizon_factor,
        growth_adjusted=growth_adjusted,
        recommended_alloc_pct=recommended_alloc_pct,
        effective_demand=effective_demand,
        was_clamped=was_clamped,
    )

    return AllocationRecommendation(
        unit_name=unit.unit_name,
        recommended_alloc_pct=recommended_alloc_pct,
        effective_demand_seats=effective_demand,
        allocated_seats=0,  # Set during distribution phase
        seat_gap=0,
        fragmentation_score=0.0,
        explanation_steps=explanation,
    )


def compute_simple_allocation(
    unit: Unit,
    horizon_months: int,
    rule_config: Optional[dict] = None,
) -> AllocationRecommendation:
    """Simple mode: flat allocation % (global or per-unit) with growth/attrition projection."""
    cfg = rule_config or {}
    global_alloc = cfg.get("global_alloc_pct", DEFAULT_GLOBAL_ALLOC_PCT)
    min_alloc = cfg.get("min_alloc_pct", MIN_ALLOC_PCT)
    max_alloc = cfg.get("max_alloc_pct", MAX_ALLOC_PCT)

    hc = unit.current_total_hc
    if hc == 0:
        return AllocationRecommendation(
            unit_name=unit.unit_name,
            recommended_alloc_pct=0,
            effective_demand_seats=0,
            allocated_seats=0,
            seat_gap=0,
            fragmentation_score=0,
            explanation_steps=["Unit has 0 headcount — no allocation needed."],
        )

    # Step 1: Base alloc % — per-unit override or global default
    base_alloc = unit.seat_alloc_pct if unit.seat_alloc_pct is not None else global_alloc
    is_override = unit.seat_alloc_pct is not None

    # Step 2: Growth/attrition projection
    net_change = unit.hc_growth_pct - unit.attrition_pct
    horizon_factor = 1 + (net_change * (horizon_months / 12))
    adjusted_alloc = base_alloc * horizon_factor

    # Step 3: Clamp to policy bounds
    was_clamped = adjusted_alloc < min_alloc or adjusted_alloc > max_alloc
    recommended_alloc_pct = max(min_alloc, min(max_alloc, adjusted_alloc))

    # Step 4: Effective demand
    effective_demand = round(recommended_alloc_pct * hc)

    explanation = explain_simple_allocation(
        unit_name=unit.unit_name,
        current_hc=hc,
        base_alloc=base_alloc,
        is_override=is_override,
        global_alloc=global_alloc,
        hc_growth_pct=unit.hc_growth_pct,
        attrition_pct=unit.attrition_pct,
        horizon_months=horizon_months,
        horizon_factor=horizon_factor,
        adjusted_alloc=adjusted_alloc,
        recommended_alloc_pct=recommended_alloc_pct,
        effective_demand=effective_demand,
        was_clamped=was_clamped,
    )

    return AllocationRecommendation(
        unit_name=unit.unit_name,
        recommended_alloc_pct=recommended_alloc_pct,
        effective_demand_seats=effective_demand,
        allocated_seats=0,
        seat_gap=0,
        fragmentation_score=0.0,
        explanation_steps=explanation,
    )


def compute_all_allocations(
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    horizon_months: int,
    rule_config: Optional[dict] = None,
) -> List[AllocationRecommendation]:
    """Compute recommended allocation for all units using flat % allocation."""
    results = []
    for unit in units:
        results.append(compute_simple_allocation(unit, horizon_months, rule_config))
    return results


def distribute_seats(
    allocations: List[AllocationRecommendation],
    units: List[Unit],
    total_supply: int,
    rule_config: Optional[dict] = None,
) -> List[AllocationRecommendation]:
    """Distribute available seats to units, handling scarcity if needed."""
    cfg = rule_config or {}
    contribution_factor = cfg.get("shrink_contribution_factor", SHRINK_CONTRIBUTION_FACTOR)

    total_demand = sum(a.effective_demand_seats for a in allocations)
    unit_map = {u.unit_name: u for u in units}

    if total_demand <= total_supply:
        # No scarcity — give everyone what they need
        for alloc in allocations:
            alloc.allocated_seats = alloc.effective_demand_seats
            alloc.seat_gap = 0
        return allocations

    # Scarcity mode — redistribute
    # Step A: Sort by priority
    def sort_key(a: AllocationRecommendation):
        u = unit_map.get(a.unit_name)
        priority = PRIORITY_ORDER.get(u.business_priority if u else None, 3)
        net_growth = u.net_hc_change_pct if u else 0
        return (priority, -net_growth)  # Lower priority number first, higher growth first

    sorted_allocs = sorted(allocations, key=sort_key)

    # Step B: Shrinking units contribute back
    pool = total_supply
    for alloc in sorted_allocs:
        u = unit_map.get(alloc.unit_name)
        if u and u.net_hc_change_pct < 0:
            release = abs(u.net_hc_change_pct) * alloc.effective_demand_seats * contribution_factor
            alloc.effective_demand_seats = max(0, alloc.effective_demand_seats - round(release))

    # Recalculate total demand after releases
    total_demand = sum(a.effective_demand_seats for a in sorted_allocs)

    # Step C: Proportional allocation
    remaining = total_supply
    for alloc in sorted_allocs:
        if total_demand > 0:
            share = alloc.effective_demand_seats / total_demand
            assigned = min(alloc.effective_demand_seats, round(remaining * share))
        else:
            assigned = 0
        alloc.allocated_seats = assigned
        alloc.seat_gap = assigned - alloc.effective_demand_seats
        remaining -= assigned
        total_demand -= alloc.effective_demand_seats

    return allocations


def run_allocation(
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    floors: List[Floor],
    horizon_months: int,
    rule_config: Optional[dict] = None,
) -> List[AllocationRecommendation]:
    """Full allocation pipeline: compute recommendations then distribute seats."""
    allocations = compute_all_allocations(units, attendance_map, horizon_months, rule_config)
    total_supply = sum(f.total_seats for f in floors)
    allocations = distribute_seats(allocations, units, total_supply, rule_config)
    return allocations


def compute_rto_alerts(
    allocations: List[AllocationRecommendation],
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    rule_config: Optional[dict] = None,
) -> List[dict]:
    """Compute RTO utilization alerts for all units.

    IMPORTANT: Pass scenario-modified attendance (with RTO mandate applied) for accurate results.

    Uses attendance data (median HC, max HC, RTO days) to compute expected seats:
      expected_seats = (monthly_median_hc + peak_buffer) * (rto_days / 5)
    Falls back to (rto_days / 5) * HC when no attendance data is available.

    Returns list of dicts with: unit_name, expected_seats, allocated_seats, gap_pct, status
    """
    cfg = rule_config or {}
    threshold = cfg.get("rto_utilization_threshold", 0.20)
    buffer_mult = cfg.get("peak_buffer_multiplier", PEAK_BUFFER_MULTIPLIER)

    unit_map = {u.unit_name: u for u in units}
    alloc_map = {a.unit_name: a for a in allocations}

    alerts = []
    for unit_name, alloc in alloc_map.items():
        unit = unit_map.get(unit_name)
        att = attendance_map.get(unit_name)
        if not unit or unit.current_total_hc == 0:
            continue

        if att:
            # Use attendance data: median + peak buffer, scaled by RTO
            base_expected = att.monthly_median_hc
            peak_buffer = (att.monthly_max_hc - att.monthly_median_hc) * buffer_mult
            rto_factor = att.avg_rto_days_per_week / WORKING_DAYS_PER_WEEK
            expected_seats = round((base_expected + peak_buffer) * rto_factor)
        else:
            # Fallback when no attendance data
            expected_seats = round((3.0 / WORKING_DAYS_PER_WEEK) * unit.current_total_hc)

        if expected_seats == 0:
            continue

        allocated = alloc.allocated_seats
        gap_pct = (allocated - expected_seats) / expected_seats

        if gap_pct < -0.10:
            status = "Under-allocated"
        elif gap_pct > threshold:
            status = "Under-utilized"
        else:
            status = "Aligned"

        alerts.append({
            "unit_name": unit_name,
            "expected_seats": expected_seats,
            "allocated_seats": allocated,
            "gap_pct": gap_pct,
            "status": status,
        })

    return alerts


def compute_rto_compliance(
    attendance_map: Dict[str, AttendanceProfile],
    global_rto_target: float,
) -> List[dict]:
    """Flag units whose avg RTO days are below the global target.

    Returns list of dicts with: unit_name, actual_rto, target_rto, gap_days, compliant
    """
    results = []
    for unit_name, att in sorted(attendance_map.items()):
        gap = att.avg_rto_days_per_week - global_rto_target
        results.append({
            "unit_name": unit_name,
            "actual_rto": att.avg_rto_days_per_week,
            "target_rto": global_rto_target,
            "gap_days": gap,
            "compliant": gap >= 0,
        })
    return results
