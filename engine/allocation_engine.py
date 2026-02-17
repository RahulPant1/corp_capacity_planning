"""Rule-based allocation logic — the core business engine."""

from typing import Dict, List, Optional, Tuple
from models.unit import Unit
from models.attendance import AttendanceProfile
from models.allocation import AllocationRecommendation
from models.building import Floor
from engine.explainer import explain_allocation, explain_simple_allocation
from config.defaults import (
    MIN_ALLOC_PCT, MAX_ALLOC_PCT,
    STABILITY_DISCOUNT_THRESHOLD, STABILITY_DISCOUNT_FACTOR,
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
    stability_threshold = cfg.get("stability_discount_threshold", STABILITY_DISCOUNT_THRESHOLD)
    stability_discount = cfg.get("stability_discount_factor", STABILITY_DISCOUNT_FACTOR)
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

    stability = attendance.attendance_stability or 0.5
    adj_peak_buffer = peak_buffer
    if stability > stability_threshold:
        adj_peak_buffer = peak_buffer * (1 - stability_discount)

    # Step 3: RTO scaling (scale base, not peak buffer)
    rto_factor = attendance.avg_rto_days_per_week / WORKING_DAYS_PER_WEEK
    scaled_ratio = base_ratio * rto_factor

    # Step 4: Growth/attrition projection
    net_change = unit.hc_growth_pct - unit.attrition_pct
    horizon_factor = 1 + (net_change * (horizon_months / 12))
    growth_adjusted = scaled_ratio * horizon_factor

    # Step 5: Combine
    raw_alloc_pct = growth_adjusted + adj_peak_buffer
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
        attendance_stability=stability,
        hc_growth_pct=unit.hc_growth_pct,
        attrition_pct=unit.attrition_pct,
        horizon_months=horizon_months,
        base_ratio=base_ratio,
        peak_buffer=peak_buffer,
        adj_peak_buffer=adj_peak_buffer,
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
    """Compute recommended allocation for all units. Routes by allocation_mode."""
    cfg = rule_config or {}
    mode = cfg.get("allocation_mode", ALLOCATION_MODE)

    results = []
    for unit in units:
        if mode == "simple":
            results.append(compute_simple_allocation(unit, horizon_months, rule_config))
        else:
            att = attendance_map.get(unit.unit_name)
            if att is None:
                att = AttendanceProfile(
                    unit_name=unit.unit_name,
                    monthly_median_hc=unit.current_total_hc * 0.6,
                    monthly_max_hc=unit.current_total_hc * 0.8,
                    avg_rto_days_per_week=3.0,
                    attendance_stability=0.5,
                )
            results.append(compute_recommended_allocation(unit, att, horizon_months, rule_config))
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
