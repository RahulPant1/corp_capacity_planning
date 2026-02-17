"""Generates human-readable explanations for allocation recommendations."""

from typing import List


def explain_allocation(
    unit_name: str,
    current_hc: int,
    monthly_median_hc: float,
    monthly_max_hc: float,
    avg_rto_days: float,
    hc_growth_pct: float,
    attrition_pct: float,
    horizon_months: int,
    base_ratio: float,
    peak_buffer: float,
    rto_factor: float,
    scaled_ratio: float,
    horizon_factor: float,
    growth_adjusted: float,
    recommended_alloc_pct: float,
    effective_demand: int,
    was_clamped: bool,
) -> List[str]:
    """Produce step-by-step explanation for an allocation recommendation."""
    steps = []

    steps.append(
        f"Step 1 - Base demand: Median in-office strength is {monthly_median_hc:.0f} "
        f"out of {current_hc} HC => base ratio {base_ratio:.1%}"
    )

    steps.append(
        f"Step 2 - Peak buffer: Peak HC ({monthly_max_hc:.0f}) adds {peak_buffer:.1%} buffer"
    )

    steps.append(
        f"Step 3 - RTO scaling: {avg_rto_days} days/week => "
        f"scaling factor {rto_factor:.2f}, scaled ratio {scaled_ratio:.1%}"
    )

    net_change = hc_growth_pct - attrition_pct
    steps.append(
        f"Step 4 - Growth/Attrition: Growth {hc_growth_pct:+.1%}, Attrition {attrition_pct:+.1%} "
        f"=> net {net_change:+.1%} over {horizon_months}mo => factor {horizon_factor:.3f}"
    )

    steps.append(
        f"Step 5 - Final: {growth_adjusted:.1%} (growth-adjusted) + {peak_buffer:.1%} (buffer) "
        f"= {recommended_alloc_pct:.1%} recommended allocation"
    )

    if was_clamped:
        steps.append(
            f"Note: Allocation was clamped to policy bounds => final {recommended_alloc_pct:.1%}"
        )

    steps.append(
        f"Step 6 - Effective demand: {recommended_alloc_pct:.1%} x {current_hc} HC "
        f"= {effective_demand} seats needed"
    )

    return steps


def explain_simple_allocation(
    unit_name: str,
    current_hc: int,
    base_alloc: float,
    is_override: bool,
    global_alloc: float,
    hc_growth_pct: float,
    attrition_pct: float,
    horizon_months: int,
    horizon_factor: float,
    adjusted_alloc: float,
    recommended_alloc_pct: float,
    effective_demand: int,
    was_clamped: bool,
) -> List[str]:
    """Produce step-by-step explanation for a simple-mode allocation."""
    steps = []

    if is_override:
        steps.append(
            f"Step 1 - Allocation %: Unit override = {base_alloc:.0%} "
            f"(global default is {global_alloc:.0%})"
        )
    else:
        steps.append(
            f"Step 1 - Allocation %: Global default = {base_alloc:.0%}"
        )

    net_change = hc_growth_pct - attrition_pct
    steps.append(
        f"Step 2 - Growth/Attrition: Growth {hc_growth_pct:+.1%}, Attrition {attrition_pct:+.1%} "
        f"=> net {net_change:+.1%} over {horizon_months}mo => factor {horizon_factor:.3f}"
    )

    steps.append(
        f"Step 3 - Adjusted allocation: {base_alloc:.0%} x {horizon_factor:.3f} "
        f"= {adjusted_alloc:.1%}"
    )

    if was_clamped:
        steps.append(
            f"Note: Allocation clamped to policy bounds => {recommended_alloc_pct:.1%}"
        )

    steps.append(
        f"Step 4 - Effective demand: {recommended_alloc_pct:.1%} x {current_hc} HC "
        f"= {effective_demand} seats needed"
    )

    return steps
