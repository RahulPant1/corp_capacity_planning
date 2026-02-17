"""Tab 2: Unit Impact View — transparency and accountability at unit level."""

import streamlit as st
import pandas as pd

from data.session_store import get_active_scenario, get_units, get_attendance, get_rule_config, is_data_loaded
from components.tables import render_risk_table
from engine.allocation_engine import compute_rto_alerts
from config.defaults import (
    RISK_RED_GAP_PCT, RISK_RED_FRAGMENTATION,
    RISK_AMBER_GAP_PCT, RISK_AMBER_FRAGMENTATION,
)


def _compute_risk_level(gap_pct: float, fragmentation: float) -> str:
    if gap_pct < RISK_RED_GAP_PCT or fragmentation > RISK_RED_FRAGMENTATION:
        return "RED"
    elif gap_pct < RISK_AMBER_GAP_PCT or fragmentation > RISK_AMBER_FRAGMENTATION:
        return "AMBER"
    return "GREEN"


def render(sidebar_state):
    """Render the Unit Impact View tab."""
    st.header("Unit Impact View")

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario or not scenario.allocation_results:
        st.info("No allocation results available. Run a simulation from the Scenario Lab.")
        return

    allocations = scenario.allocation_results
    units = get_units()
    unit_map = {u.unit_name: u for u in units}

    # Compute RTO alerts
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}
    rto_alerts = compute_rto_alerts(allocations, units, att_map, get_rule_config())
    rto_status_map = {ra["unit_name"]: ra for ra in rto_alerts}

    # --- Filters ---
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        priorities = sorted(set(u.business_priority or "None" for u in units))
        selected_priorities = st.multiselect("Filter by Priority", priorities, default=priorities)
    with col_f2:
        risk_filter = st.multiselect("Filter by Risk", ["RED", "AMBER", "GREEN"],
                                      default=["RED", "AMBER", "GREEN"])
    with col_f3:
        search = st.text_input("Search Unit Name", "")

    # --- Build table ---
    rows = []
    for a in allocations:
        u = unit_map.get(a.unit_name)
        if not u:
            continue

        priority = u.business_priority or "None"
        if priority not in selected_priorities:
            continue

        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
        risk = _compute_risk_level(gap_pct, a.fragmentation_score)

        if risk not in risk_filter:
            continue

        if search and search.lower() not in a.unit_name.lower():
            continue

        projected_hc = round(u.projected_hc(scenario.planning_horizon_months))

        rto_info = rto_status_map.get(a.unit_name)
        rto_status = rto_info["status"] if rto_info else "N/A"

        rows.append({
            "Unit": a.unit_name,
            "Priority": priority,
            "Current HC": u.current_total_hc,
            "Projected HC": projected_hc,
            "Growth %": f"{u.hc_growth_pct:.1%}",
            "Attrition %": f"{u.attrition_pct:.1%}",
            "Alloc %": f"{a.recommended_alloc_pct:.1%}",
            "Overridden": "Yes" if a.is_overridden else "",
            "Demand (seats)": a.effective_demand_seats,
            "Allocated": a.allocated_seats,
            "Gap": a.seat_gap,
            "Gap %": f"{gap_pct:.1%}",
            "Fragmentation": f"{a.fragmentation_score:.2f}",
            "Risk Level": risk,
            "RTO Status": rto_status,
        })

    if not rows:
        st.info("No units match the current filters.")
        return

    df = pd.DataFrame(rows)
    render_risk_table(df)

    # --- Export ---
    csv = df.to_csv(index=False)
    st.download_button("Export Unit Impact (CSV)", csv, "unit_impact.csv", "text/csv")

    # --- Unit Detail Expander ---
    st.divider()
    st.subheader("Unit Detail")

    selected_unit = st.selectbox(
        "Select a unit for detailed view",
        [a.unit_name for a in allocations],
        key="unit_detail_select",
    )

    if selected_unit:
        alloc = next((a for a in allocations if a.unit_name == selected_unit), None)
        if alloc:
            st.markdown("**Allocation Explanation:**")
            for step in alloc.explanation_steps:
                st.markdown(f"- {step}")

            # Floor assignments for this unit
            unit_floors = [a for a in scenario.floor_assignments if a.unit_name == selected_unit]
            if unit_floors:
                st.markdown("**Floor Assignments:**")
                floor_data = [{
                    "Tower": a.tower_id,
                    "Floor": a.floor_number,
                    "Seats": a.seats_assigned,
                    "Adjacency": a.adjacency_tier,
                } for a in unit_floors]
                st.dataframe(pd.DataFrame(floor_data), use_container_width=True)
