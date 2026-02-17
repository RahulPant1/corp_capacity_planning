"""Tab 4: Scenario Lab — controlled experimentation with planning assumptions."""

import streamlit as st
import pandas as pd
import copy

from data.session_store import (
    get_active_scenario, get_scenarios, get_units, get_attendance, get_floors,
    get_rule_config, update_scenario, add_audit_entry, is_data_loaded,
    get_active_scenario_id,
)
from models.scenario import ScenarioOverride, ScenarioParams
from engine.scenario_engine import run_scenario, compare_scenarios
from components.tables import render_comparison_table
from components.charts import scenario_comparison_bar


def render(sidebar_state):
    """Render the Scenario Lab tab."""
    st.header("Scenario Lab")

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenarios = get_scenarios()
    scenario = get_active_scenario()

    if not scenario:
        st.info("No active scenario. Create one in Admin & Governance.")
        return

    if scenario.is_locked:
        st.warning(f"Scenario '{scenario.name}' is locked. Changes are disabled.")

    # --- Scenario Header ---
    st.subheader(f"Scenario: {scenario.name}")
    st.caption(f"Type: {scenario.scenario_type} | Horizon: {scenario.planning_horizon_months} months")

    st.divider()

    # --- Scenario-Wide Controls ---
    st.subheader("Scenario-Wide Controls")

    col1, col2, col3 = st.columns(3)
    with col1:
        rto_mandate = st.slider(
            "Global RTO Mandate (days/week)",
            min_value=0.0, max_value=5.0,
            value=scenario.params.global_rto_mandate_days or 0.0,
            step=0.5,
            key="scenario_rto_mandate",
            disabled=scenario.is_locked,
        )
    with col2:
        capacity_reduction_int = st.slider(
            "Capacity Reduction %",
            min_value=0, max_value=30,
            value=round(scenario.params.capacity_reduction_pct * 100),
            step=5,
            key="scenario_capacity_reduction",
            disabled=scenario.is_locked,
        )
        capacity_reduction = capacity_reduction_int / 100.0
    with col3:
        floors = get_floors()
        all_floor_ids = sorted(set(f.floor_id for f in floors))
        excluded = st.multiselect(
            "Excluded Floors",
            all_floor_ids,
            default=scenario.params.excluded_floors,
            key="scenario_excluded_floors",
            disabled=scenario.is_locked,
        )

    st.divider()

    # --- Unit-Level Override Table ---
    st.subheader("Unit-Level Overrides")

    units = get_units()
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}

    # Build editable dataframe
    rows = []
    for u in units:
        att = att_map.get(u.unit_name)
        override = scenario.unit_overrides.get(u.unit_name, ScenarioOverride(unit_name=u.unit_name))

        rows.append({
            "Unit": u.unit_name,
            "Baseline Growth %": u.hc_growth_pct * 100,
            "Scenario Growth %": (override.hc_growth_pct or u.hc_growth_pct) * 100,
            "Baseline Attrition %": u.attrition_pct * 100,
            "Scenario Attrition %": (override.attrition_pct or u.attrition_pct) * 100,
            "Baseline RTO Days": att.avg_rto_days_per_week if att else 3.0,
            "Scenario RTO Days": override.avg_rto_days or (att.avg_rto_days_per_week if att else 3.0),
            "Alloc % Override": (override.alloc_pct_override or 0) * 100,
        })

    edit_df = pd.DataFrame(rows)

    if not scenario.is_locked:
        edited = st.data_editor(
            edit_df,
            disabled=["Unit", "Baseline Growth %", "Baseline Attrition %", "Baseline RTO Days"],
            use_container_width=True,
            key="scenario_unit_editor",
            num_rows="fixed",
        )
    else:
        st.dataframe(edit_df, use_container_width=True)
        edited = edit_df

    st.divider()

    # --- Action Buttons ---
    st.subheader("Actions")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        run_sim = st.button(
            "🚀 Run Simulation",
            type="primary",
            disabled=scenario.is_locked,
            key="btn_run_sim",
        )

    with col2:
        apply_rules = st.button(
            "📐 Apply Rules",
            disabled=scenario.is_locked,
            key="btn_apply_rules",
        )

    with col3:
        reset = st.button(
            "🔄 Reset Scenario",
            disabled=scenario.is_locked,
            key="btn_reset",
        )

    with col4:
        compare = st.button(
            "📊 Compare with Baseline",
            key="btn_compare",
        )

    if (run_sim or apply_rules) and not scenario.is_locked:
        # Extract overrides from edited table
        overrides = {}
        for _, row in edited.iterrows():
            unit_name = row["Unit"]
            base_unit = next((u for u in units if u.unit_name == unit_name), None)
            if not base_unit:
                continue

            att = att_map.get(unit_name)
            base_rto = att.avg_rto_days_per_week if att else 3.0

            override = ScenarioOverride(unit_name=unit_name)
            has_change = False

            if abs(row["Scenario Growth %"] - base_unit.hc_growth_pct * 100) > 0.01:
                override.hc_growth_pct = row["Scenario Growth %"] / 100.0
                has_change = True
            if abs(row["Scenario Attrition %"] - base_unit.attrition_pct * 100) > 0.01:
                override.attrition_pct = row["Scenario Attrition %"] / 100.0
                has_change = True
            if abs(row["Scenario RTO Days"] - base_rto) > 0.01:
                override.avg_rto_days = row["Scenario RTO Days"]
                has_change = True
            if row["Alloc % Override"] > 0:
                override.alloc_pct_override = row["Alloc % Override"] / 100.0
                has_change = True

            if has_change:
                overrides[unit_name] = override

        # Update scenario params
        scenario.unit_overrides = overrides
        scenario.params = ScenarioParams(
            global_rto_mandate_days=rto_mandate if rto_mandate > 0 else None,
            excluded_floors=excluded,
            capacity_reduction_pct=capacity_reduction,
        )

        # Run simulation
        att_map_full = {a.unit_name: a for a in attendance_profiles}
        scenario = run_scenario(
            scenario, units, att_map_full, floors, get_rule_config(),
        )
        update_scenario(scenario)
        add_audit_entry(
            "simulation", scenario.scenario_id, "all",
            "", f"Ran with {len(overrides)} overrides",
        )
        st.success(f"Simulation complete for '{scenario.name}'.")
        st.rerun()

    if reset and not scenario.is_locked:
        scenario.unit_overrides = {}
        scenario.params = ScenarioParams()
        scenario.allocation_results = []
        scenario.floor_assignments = []
        update_scenario(scenario)
        add_audit_entry("reset", scenario.scenario_id, "all", "", "reset")
        st.success("Scenario reset to defaults.")
        st.rerun()

    if compare:
        baseline = scenarios.get("baseline")
        if not baseline or not baseline.allocation_results:
            st.warning("Baseline has no results. Run simulation on baseline first.")
        elif not scenario.allocation_results:
            st.warning("Current scenario has no results. Run simulation first.")
        else:
            diffs = compare_scenarios(baseline, scenario)
            diff_df = pd.DataFrame(diffs)

            st.subheader(f"Comparison: Baseline vs {scenario.name}")
            render_comparison_table(diff_df)

            fig = scenario_comparison_bar(diff_df)
            st.plotly_chart(fig, use_container_width=True)

    # --- Current Results Summary ---
    if scenario.allocation_results:
        st.divider()
        st.subheader("Current Scenario Results")

        result_rows = []
        for a in scenario.allocation_results:
            result_rows.append({
                "Unit": a.unit_name,
                "Alloc %": f"{a.recommended_alloc_pct:.1%}",
                "Demand": a.effective_demand_seats,
                "Allocated": a.allocated_seats,
                "Gap": a.seat_gap,
                "Fragmentation": f"{a.fragmentation_score:.2f}",
                "Overridden": "Yes" if a.is_overridden else "",
            })

        st.dataframe(pd.DataFrame(result_rows), use_container_width=True)
