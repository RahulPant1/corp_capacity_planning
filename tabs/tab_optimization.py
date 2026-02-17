"""Tab 5: Optimization & Recommendations — LP-based best-fit allocations."""

import streamlit as st
import pandas as pd

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_rule_config,
    get_attendance,
    update_scenario, add_audit_entry, is_data_loaded,
)
from engine.optimizer import optimize_allocation
from engine.scenario_engine import apply_floor_modifications, apply_overrides
from components.tables import render_comparison_table


def render(sidebar_state):
    """Render the Optimization & Recommendations tab."""
    st.header("Optimization & Recommendations")

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario or not scenario.allocation_results:
        st.info("No allocation results available. Run a simulation from the Scenario Lab first.")
        return

    if scenario.is_locked:
        st.warning(f"Scenario '{scenario.name}' is locked. Optimization results cannot be applied.")

    # --- Objective Selection ---
    st.subheader("Optimization Objective")

    objectives = {
        "optimal_placement": "Optimal Placement — seat everyone per allocation rule on fewest floors",
        "rto_based": "RTO-Based — allocate by actual attendance patterns, free unused capacity",
        "rto_whatif": "What-If RTO — simulate a different RTO policy (e.g., 3 or 4 days/week)",
    }

    selected_obj = st.radio(
        "Select optimization objective",
        options=list(objectives.keys()),
        format_func=lambda k: objectives[k],
        key="opt_objective",
    )

    # RTO What-If slider
    target_rto = None
    if selected_obj == "rto_whatif":
        target_rto = st.slider(
            "Target RTO days/week for all units",
            min_value=1.0, max_value=5.0, value=3.0, step=0.5,
            key="opt_rto_target",
        )

    # --- Compute effective floors ---
    config = get_rule_config()
    raw_floors = get_floors()
    effective_floors = apply_floor_modifications(raw_floors, scenario)
    units = get_units()

    raw_total = sum(f.total_seats for f in raw_floors)
    effective_total = sum(f.total_seats for f in effective_floors)

    # Build attendance map (with scenario overrides applied)
    att_profiles = get_attendance()
    att_map_raw = {a.unit_name: a for a in att_profiles}
    _, scenario_att_map = apply_overrides(units, att_map_raw, scenario)

    # --- Constraint Visibility ---
    with st.expander("Active Constraints", expanded=False):
        if len(effective_floors) < len(raw_floors) or effective_total < raw_total:
            st.markdown(
                f"- **Floor capacity**: {len(raw_floors)} floors ({raw_total:,} seats) "
                f"-> **{len(effective_floors)} floors ({effective_total:,} seats)** after scenario adjustments"
            )
        else:
            st.markdown(f"- **Floor capacity**: {len(effective_floors)} floors, "
                        f"{effective_total:,} total seats")
        st.markdown(f"- **Global allocation %**: {config.get('global_alloc_pct', 0.80):.0%}")
        st.markdown(f"- **Units**: {len(units)}")
        if scenario.params.excluded_floors:
            st.markdown(f"- **Excluded floors**: {', '.join(scenario.params.excluded_floors)}")
        if scenario.params.capacity_reduction_pct > 0:
            st.markdown(f"- **Capacity reduction**: {scenario.params.capacity_reduction_pct:.0%}")
        if selected_obj in ("rto_based", "rto_whatif"):
            st.markdown(f"- **Demand basis**: Attendance data (Median HC + Peak Buffer x RTO)")
            if selected_obj == "rto_whatif" and target_rto:
                st.markdown(f"- **Target RTO**: {target_rto} days/week for all units")

    st.divider()

    # --- Run Optimization ---
    col1, col2 = st.columns([1, 3])
    with col1:
        run_opt = st.button("Run Optimization", type="primary", key="btn_run_opt")

    if run_opt:
        with st.spinner("Running optimization..."):
            result = optimize_allocation(
                allocations=scenario.allocation_results,
                floors=effective_floors,
                baseline_assignments=scenario.floor_assignments,
                objective=selected_obj,
                excluded_floor_ids=[],
                units=units,
                attendance_map=scenario_att_map,
                rule_config=config,
                target_rto_days=target_rto,
            )

        st.session_state["optimization_result"] = result

    # --- Display Results ---
    result = st.session_state.get("optimization_result")
    if result:
        st.divider()
        st.subheader("Optimization Results")

        # Status
        if "Optimal" in result.status:
            st.success(f"Status: {result.status}")
        else:
            st.error(f"Status: {result.status}")
            if result.message:
                st.warning(result.message)
            return

        st.info(result.message)

        # Savings summary for RTO objectives
        if result.savings_summary:
            sv = result.savings_summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Allocation Rule Seats", f"{sv['allocation_rule_seats']:,}")
            col2.metric("RTO-Based Seats", f"{sv['rto_based_seats']:,}")
            col3.metric("Seats Saved", f"{sv['seats_saved']:,}",
                        delta=f"{sv['seats_saved']:+,}", delta_color="normal" if sv['seats_saved'] >= 0 else "inverse")
            col4.metric("Floors Freed", sv['floors_freed'],
                        delta=f"{sv['floors_freed']:+d}", delta_color="normal" if sv['floors_freed'] >= 0 else "inverse")

        # Before/After comparison
        st.subheader("Before / After Comparison")
        if result.before_after:
            ba_df = pd.DataFrame(result.before_after)
            render_comparison_table(ba_df)

            # Impact summary
            helped = sum(1 for r in result.before_after if r["Seat Change"] > 0)
            impacted = sum(1 for r in result.before_after if r["Seat Change"] < 0)
            unchanged = sum(1 for r in result.before_after if r["Seat Change"] == 0)

            total_before = sum(r["Before Seats"] for r in result.before_after)
            total_after = sum(r["After Seats"] for r in result.before_after)
            total_floors_before = sum(r["Before Floors"] for r in result.before_after)
            total_floors_after = sum(r["After Floors"] for r in result.before_after)

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Seats", f"{total_after:,}",
                        delta=f"{total_after - total_before:+,}")
            col2.metric("Total Floor Assignments", total_floors_after,
                        delta=f"{total_floors_after - total_floors_before:+d}")
            col3.metric("Units Consolidated", sum(1 for r in result.before_after if r["Floor Change"] < 0))

        # Consolidation suggestions
        if result.consolidation_suggestions:
            st.subheader("Consolidation Suggestions")
            for s in result.consolidation_suggestions:
                st.info(s)

        # Accept button
        st.divider()
        if not scenario.is_locked:
            if st.button("Accept & Apply to Scenario", type="primary", key="btn_accept_opt"):
                scenario.floor_assignments = result.assignments

                for alloc in scenario.allocation_results:
                    alloc.allocated_seats = result.unit_allocations.get(alloc.unit_name, 0)
                    alloc.seat_gap = alloc.allocated_seats - alloc.effective_demand_seats

                update_scenario(scenario)
                add_audit_entry(
                    "accept_optimization", scenario.scenario_id,
                    "floor_assignments", "rule-based", f"optimized ({selected_obj})",
                    rationale=f"Accepted {selected_obj} optimization",
                )
                st.success("Optimization results applied to scenario.")
                st.info("Dashboard, Spatial View, and Unit Impact now reflect the optimized allocation.")
                st.session_state.pop("optimization_result", None)
                st.rerun()
        else:
            st.warning("Cannot apply — scenario is locked.")
