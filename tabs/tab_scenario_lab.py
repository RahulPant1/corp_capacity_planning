"""Tab 4: Scenario Lab — controlled experimentation with planning assumptions."""

import streamlit as st
import pandas as pd
import copy

from data.session_store import (
    get_active_scenario, get_scenarios, get_units, get_attendance, get_floors,
    get_rule_config, update_scenario, add_audit_entry, is_data_loaded,
    get_active_scenario_id, get_last_data_edit,
)
from models.scenario import ScenarioOverride, ScenarioParams
from engine.scenario_engine import run_scenario, compare_scenarios
from engine.allocation_engine import compute_rto_alerts
from components.tables import render_comparison_table
from components.charts import scenario_comparison_bar
from config.defaults import (
    RISK_RED_GAP_PCT, RISK_RED_FRAGMENTATION,
    RISK_AMBER_GAP_PCT, RISK_AMBER_FRAGMENTATION,
)


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

    # Stale-data warning
    last_edit = get_last_data_edit()
    if last_edit and (scenario.last_run_at is None or last_edit > scenario.last_run_at):
        st.warning(
            "Base data has changed since the last simulation. "
            "Re-run the simulation to see updated results."
        )

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

    rule_config = get_rule_config()
    alloc_mode = rule_config.get("allocation_mode", "simple")

    units = get_units()
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}

    if alloc_mode == "simple":
        st.caption(
            "Simple allocation mode — overrides affect growth, attrition, and allocation %. "
            "RTO days are not used for allocation in this mode."
        )

    # Build editable dataframe — scenario values only (pre-filled from baseline)
    rows = []
    for u in units:
        att = att_map.get(u.unit_name)
        override = scenario.unit_overrides.get(u.unit_name, ScenarioOverride(unit_name=u.unit_name))

        row = {
            "Unit": u.unit_name,
            "Growth %": (override.hc_growth_pct or u.hc_growth_pct) * 100,
            "Attrition %": (override.attrition_pct or u.attrition_pct) * 100,
        }

        if alloc_mode == "advanced":
            row["RTO Days"] = override.avg_rto_days or (att.avg_rto_days_per_week if att else 3.0)

        row["Alloc % Override"] = (override.alloc_pct_override or 0) * 100
        rows.append(row)

    edit_df = pd.DataFrame(rows)

    if not scenario.is_locked:
        edited = st.data_editor(
            edit_df,
            disabled=["Unit"],
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
    col1, col2 = st.columns(2)

    with col1:
        run_sim = st.button(
            "Run Simulation",
            type="primary",
            disabled=scenario.is_locked,
            key="btn_run_sim",
        )

    with col2:
        reset = st.button(
            "Reset Scenario",
            disabled=scenario.is_locked,
            key="btn_reset",
        )

    if run_sim and not scenario.is_locked:
        # Extract overrides from edited table
        overrides = {}
        for _, row in edited.iterrows():
            unit_name = row["Unit"]
            base_unit = next((u for u in units if u.unit_name == unit_name), None)
            if not base_unit:
                continue

            override = ScenarioOverride(unit_name=unit_name)
            has_change = False

            if abs(row["Growth %"] - base_unit.hc_growth_pct * 100) > 0.01:
                override.hc_growth_pct = row["Growth %"] / 100.0
                has_change = True
            if abs(row["Attrition %"] - base_unit.attrition_pct * 100) > 0.01:
                override.attrition_pct = row["Attrition %"] / 100.0
                has_change = True
            if alloc_mode == "advanced" and "RTO Days" in row:
                att = att_map.get(unit_name)
                base_rto = att.avg_rto_days_per_week if att else 3.0
                if abs(row["RTO Days"] - base_rto) > 0.01:
                    override.avg_rto_days = row["RTO Days"]
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

        # --- Scenario Impact Summary (English narrative) ---
        st.divider()
        st.subheader("Scenario Impact Summary")

        allocs = scenario.allocation_results
        total_demand = sum(a.effective_demand_seats for a in allocs)
        total_allocated = sum(a.allocated_seats for a in allocs)
        total_gap = total_allocated - total_demand
        num_units = len(allocs)

        st.markdown(
            f"This scenario allocates **{total_allocated:,} seats** across "
            f"**{num_units} units**. Total demand is **{total_demand:,} seats**, "
            f"leaving a net gap of **{total_gap:+,} seats**."
        )

        # Per-unit highlights
        unit_map_summary = {u.unit_name: u for u in units}
        highlights = []
        for a in allocs:
            u = unit_map_summary.get(a.unit_name)
            priority = (u.business_priority or "—") if u else "—"
            gap_label = f"{a.seat_gap:+d} seat {'shortfall' if a.seat_gap < 0 else 'surplus'}"
            highlights.append(
                f"**{a.unit_name}**: {a.recommended_alloc_pct:.1%} allocation "
                f"-> {a.effective_demand_seats} needed, {a.allocated_seats} allocated "
                f"({gap_label}, {priority} priority)"
            )
        with st.expander("Per-Unit Details", expanded=False):
            for h in highlights:
                st.markdown(f"- {h}")

        # Key risks (RED/AMBER units)
        risk_units = []
        for a in allocs:
            gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
            if gap_pct < RISK_RED_GAP_PCT or a.fragmentation_score > RISK_RED_FRAGMENTATION:
                risk_units.append((a.unit_name, "RED", gap_pct, a.fragmentation_score))
            elif gap_pct < RISK_AMBER_GAP_PCT or a.fragmentation_score > RISK_AMBER_FRAGMENTATION:
                risk_units.append((a.unit_name, "AMBER", gap_pct, a.fragmentation_score))

        if risk_units:
            st.markdown("**Key Risks:**")
            for name, level, gp, frag in risk_units:
                reason_parts = []
                if gp < RISK_AMBER_GAP_PCT:
                    reason_parts.append(f"seat shortfall {gp:.0%}")
                if frag > RISK_AMBER_FRAGMENTATION:
                    reason_parts.append(f"high fragmentation {frag:.2f}")
                reason = ", ".join(reason_parts)
                st.markdown(f"- :{'red' if level == 'RED' else 'orange'}[{level}] **{name}** — {reason}")

        # RTO utilization alerts
        att_profiles = get_attendance()
        att_map_rto = {a.unit_name: a for a in att_profiles}
        rto_alerts = compute_rto_alerts(allocs, units, att_map_rto, get_rule_config())
        rto_issues = [ra for ra in rto_alerts if ra["status"] != "Aligned"]
        if rto_issues:
            st.markdown("**RTO Utilization Alerts:**")
            for ra in rto_issues:
                if ra["status"] == "Under-allocated":
                    st.markdown(
                        f"- :red[UNDER-ALLOCATED] **{ra['unit_name']}**: "
                        f"allocated {ra['allocated_seats']} seats but RTO-based need is "
                        f"{ra['expected_seats']} ({ra['gap_pct']:+.0%})"
                    )
                else:
                    st.markdown(
                        f"- :orange[UNDER-UTILIZED] **{ra['unit_name']}**: "
                        f"allocated {ra['allocated_seats']} seats but RTO-based need is only "
                        f"{ra['expected_seats']} ({ra['gap_pct']:+.0%})"
                    )

        # --- Auto Baseline Comparison ---
        if scenario.scenario_id != "baseline":
            baseline = scenarios.get("baseline")
            if baseline and baseline.allocation_results:
                st.divider()
                st.subheader(f"Changes vs Baseline")

                diffs = compare_scenarios(baseline, scenario)
                diff_df = pd.DataFrame(diffs)

                # Text summary
                gained = sum(1 for d in diffs if d["Seat Change"] > 0)
                lost = sum(1 for d in diffs if d["Seat Change"] < 0)
                net_change = sum(d["Seat Change"] for d in diffs)
                st.markdown(
                    f"Compared to baseline: **{gained} units gained seats**, "
                    f"**{lost} units lost seats**. "
                    f"Net change: **{net_change:+,} seats**."
                )

                render_comparison_table(diff_df)
                fig = scenario_comparison_bar(diff_df)
                st.plotly_chart(fig, use_container_width=True)
