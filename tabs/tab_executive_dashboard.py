"""Tab 1: Executive Dashboard — high-level planning health and feasibility."""

import streamlit as st
import pandas as pd

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_attendance,
    get_rule_config, is_data_loaded, get_last_data_edit,
)
from components.metrics_cards import render_metric_row
from components.charts import capacity_vs_demand_bar, utilization_donut, rto_need_vs_allocated_bar
from engine.spatial import get_floor_utilization
from engine.allocation_engine import compute_rto_alerts
from engine.scenario_engine import apply_floor_modifications, apply_overrides
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

    # Collect alerts by category
    capacity_alerts = []
    rto_alerts_list = []
    other_alerts = []

    # Floor saturation alerts
    for fu in floor_util:
        if fu["utilization_pct"] > FLOOR_SATURATION_THRESHOLD:
            capacity_alerts.append({
                "Floor": fu["floor_id"],
                "Status": "Saturated",
                "Used / Total": f"{fu['used_seats']} / {fu['total_seats']}",
                "Utilization": f"{fu['utilization_pct']:.0%}",
            })

    # Unit shortfall alerts
    for a in allocations:
        if a.effective_demand_seats > 0:
            gap_pct = a.seat_gap / a.effective_demand_seats
            if gap_pct < UNIT_SHORTFALL_THRESHOLD:
                capacity_alerts.append({
                    "Floor": a.unit_name,
                    "Status": "Shortfall",
                    "Used / Total": f"{a.allocated_seats} / {a.effective_demand_seats}",
                    "Utilization": f"{gap_pct:+.0%}",
                })

    # RTO compliance alerts (units below global RTO target)
    units = get_units()
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}

    # RTO utilization data (use scenario-modified attendance for RTO mandate)
    _, scenario_att_map = apply_overrides(units, att_map, scenario)
    rto_alerts_data = compute_rto_alerts(allocations, units, scenario_att_map, get_rule_config())
    rto_chart_data = [ra for ra in rto_alerts_data if ra["status"] != "Aligned"]
    rto_all_data = rto_alerts_data  # all units for chart
    for ra in rto_chart_data:
        rto_alerts_list.append({
            "Unit": ra["unit_name"],
            "Alert": ra["status"],
            "Allocated": ra["allocated_seats"],
            "RTO Need": ra["expected_seats"],
        })

    # Fragmentation alerts
    for a in allocations:
        if a.fragmentation_score > 0.7:
            other_alerts.append({
                "Unit": a.unit_name,
                "Alert": "High Fragmentation",
                "Detail": f"Score: {a.fragmentation_score:.2f}",
            })

    # Cross-building spread alerts
    from collections import defaultdict
    unit_bldg_map = defaultdict(lambda: defaultdict(int))
    for a in assignments:
        unit_bldg_map[a.unit_name][a.building_id] += 1
    for unit_name, bldgs in unit_bldg_map.items():
        if len(bldgs) > 1:
            detail_parts = [f"{bid} ({cnt} floor{'s' if cnt > 1 else ''})"
                            for bid, cnt in sorted(bldgs.items())]
            other_alerts.append({
                "Unit": unit_name,
                "Alert": "Cross-Building Spread",
                "Detail": f"Across {', '.join(detail_parts)}",
            })

    has_any = capacity_alerts or rto_all_data or other_alerts

    if not has_any:
        st.success("No planning alerts — all metrics within acceptable ranges.")
    else:
        if capacity_alerts:
            st.error(f"{len(capacity_alerts)} Capacity Alert{'s' if len(capacity_alerts) != 1 else ''}")
            st.dataframe(pd.DataFrame(capacity_alerts), use_container_width=True, hide_index=True)

        if rto_all_data:
            st.subheader("RTO-Based Need vs Allocated")
            fig = rto_need_vs_allocated_bar(rto_all_data)
            st.plotly_chart(fig, use_container_width=True)
            if rto_alerts_list:
                st.warning(f"{len(rto_alerts_list)} unit{'s' if len(rto_alerts_list) != 1 else ''} with allocation mismatch")
                st.dataframe(pd.DataFrame(rto_alerts_list), use_container_width=True, hide_index=True)

        if other_alerts:
            st.info(f"{len(other_alerts)} Other Alert{'s' if len(other_alerts) != 1 else ''}")
            st.dataframe(pd.DataFrame(other_alerts), use_container_width=True, hide_index=True)
