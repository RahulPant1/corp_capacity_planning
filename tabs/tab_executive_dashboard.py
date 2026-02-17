"""Tab 1: Executive Dashboard — high-level planning health and feasibility."""

import streamlit as st
import pandas as pd

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_attendance,
    get_rule_config, is_data_loaded, get_last_data_edit,
)
from components.metrics_cards import render_metric_row
from components.charts import capacity_vs_demand_bar, utilization_donut
from engine.spatial import get_floor_utilization
from engine.allocation_engine import compute_rto_alerts
from engine.scenario_engine import apply_floor_modifications
from config.defaults import FLOOR_SATURATION_THRESHOLD, UNIT_SHORTFALL_THRESHOLD


def render(sidebar_state):
    """Render the Executive Dashboard tab."""
    st.header("Executive Dashboard")

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario or not scenario.allocation_results:
        st.info("No allocation results available. Run a simulation from the Scenario Lab.")
        return

    # Stale-data warning
    last_edit = get_last_data_edit()
    if last_edit and (scenario.last_run_at is None or last_edit > scenario.last_run_at):
        st.warning(
            "Base data has changed since the last simulation. "
            "Go to Scenario Lab and re-run to see updated results."
        )

    allocations = scenario.allocation_results
    assignments = scenario.floor_assignments
    floors = get_floors()

    # Compute effective supply (accounting for scenario exclusions + capacity reduction)
    effective_floors = apply_floor_modifications(floors, scenario)
    raw_total_seats = sum(f.total_seats for f in floors)
    effective_total_seats = sum(f.total_seats for f in effective_floors)
    has_scenario_adjustments = effective_total_seats < raw_total_seats

    # --- KPI Metrics ---
    total_demand = sum(a.effective_demand_seats for a in allocations)
    total_allocated = sum(a.allocated_seats for a in allocations)
    seat_gap = total_allocated - total_demand
    impacted_units = sum(1 for a in allocations if a.seat_gap < 0)

    supply_label = "Effective Supply" if has_scenario_adjustments else "Total Seats (Supply)"
    supply_metrics = {"label": supply_label, "value": f"{effective_total_seats:,}"}
    if has_scenario_adjustments:
        supply_metrics["delta"] = f"of {raw_total_seats:,} base seats"
        supply_metrics["delta_color"] = "off"

    render_metric_row([
        supply_metrics,
        {"label": "Total Demand", "value": f"{total_demand:,}"},
        {"label": "Seat Gap", "value": f"{seat_gap:+,}",
         "delta": f"{seat_gap:+,}", "delta_color": "normal" if seat_gap >= 0 else "inverse"},
        {"label": "Units with Shortfall", "value": str(impacted_units),
         "delta": f"{impacted_units} units" if impacted_units > 0 else "None",
         "delta_color": "inverse" if impacted_units > 0 else "normal"},
    ])

    # Scenario adjustment info
    if has_scenario_adjustments:
        notes = []
        if scenario.params.excluded_floors:
            notes.append(f"{len(scenario.params.excluded_floors)} floors excluded ({', '.join(scenario.params.excluded_floors)})")
        if scenario.params.capacity_reduction_pct > 0:
            notes.append(f"{scenario.params.capacity_reduction_pct:.0%} capacity reduction applied")
        st.info(f"Scenario adjustments: {'; '.join(notes)}. "
                f"Effective supply is {effective_total_seats:,} seats (base: {raw_total_seats:,}).")

    st.divider()

    # --- Charts ---
    col1, col2 = st.columns([3, 2])

    with col1:
        # Capacity vs demand by tower
        floor_util = get_floor_utilization(floors, assignments)
        tower_summary = {}
        for fu in floor_util:
            tid = fu["tower_id"]
            if tid not in tower_summary:
                tower_summary[tid] = {"tower_id": tid, "total_seats": 0, "used_seats": 0}
            tower_summary[tid]["total_seats"] += fu["total_seats"]
            tower_summary[tid]["used_seats"] += fu["used_seats"]

        fig = capacity_vs_demand_bar(list(tower_summary.values()))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = utilization_donut(total_allocated, effective_total_seats)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Alerts ---
    st.subheader("Planning Alerts")

    alerts = []

    # Floor saturation alerts
    for fu in floor_util:
        if fu["utilization_pct"] > FLOOR_SATURATION_THRESHOLD:
            alerts.append({
                "Type": "Floor Saturated",
                "Detail": f"{fu['floor_id']}: {fu['utilization_pct']:.0%} utilized "
                          f"({fu['used_seats']}/{fu['total_seats']} seats)",
                "Severity": "High",
            })

    # Unit shortfall alerts
    for a in allocations:
        if a.effective_demand_seats > 0:
            gap_pct = a.seat_gap / a.effective_demand_seats
            if gap_pct < UNIT_SHORTFALL_THRESHOLD:
                alerts.append({
                    "Type": "Unit Shortfall",
                    "Detail": f"{a.unit_name}: {a.seat_gap:+d} seats ({gap_pct:.0%} of demand)",
                    "Severity": "High",
                })

    # Fragmentation alerts
    for a in allocations:
        if a.fragmentation_score > 0.7:
            alerts.append({
                "Type": "High Fragmentation",
                "Detail": f"{a.unit_name}: fragmentation score {a.fragmentation_score:.2f}",
                "Severity": "Medium",
            })

    # RTO utilization alerts
    units = get_units()
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}
    rto_alerts = compute_rto_alerts(allocations, units, att_map, get_rule_config())
    for ra in rto_alerts:
        if ra["status"] == "Under-allocated":
            alerts.append({
                "Type": "RTO Under-allocated",
                "Detail": f"{ra['unit_name']}: allocated {ra['allocated_seats']} seats "
                          f"but RTO-based need is {ra['expected_seats']} ({ra['gap_pct']:+.0%})",
                "Severity": "High",
            })
        elif ra["status"] == "Under-utilized":
            alerts.append({
                "Type": "RTO Under-utilized",
                "Detail": f"{ra['unit_name']}: allocated {ra['allocated_seats']} seats "
                          f"but RTO-based need is only {ra['expected_seats']} ({ra['gap_pct']:+.0%})",
                "Severity": "Medium",
            })

    if alerts:
        alert_df = pd.DataFrame(alerts)
        st.dataframe(alert_df, use_container_width=True)
    else:
        st.success("No planning alerts — all metrics within acceptable ranges.")
