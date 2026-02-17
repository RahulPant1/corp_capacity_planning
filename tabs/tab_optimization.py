"""Tab 5: Optimization & Recommendations — LP-based best-fit allocations."""

import streamlit as st
import pandas as pd

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_rule_config,
    update_scenario, add_audit_entry, is_data_loaded,
)
from engine.optimizer import optimize_allocation
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
        "min_shortfall": "Minimize Seat Shortfall — reduce total unmet demand",
        "max_cohesion": "Maximize Floor Cohesion — keep units on same/adjacent floors",
        "min_floors": "Minimize Floors Used — consolidate onto fewer floors",
        "fair_allocation": "Fair Allocation — minimize worst-case shortfall ratio",
    }

    selected_obj = st.radio(
        "Select optimization objective",
        options=list(objectives.keys()),
        format_func=lambda k: objectives[k],
        key="opt_objective",
    )

    # --- Constraint Visibility ---
    with st.expander("Active Constraints", expanded=False):
        config = get_rule_config()
        floors = get_floors()
        units = get_units()

        st.markdown(f"- **Floor capacity**: {len(floors)} floors, "
                    f"{sum(f.total_seats for f in floors):,} total seats")
        st.markdown(f"- **Min allocation %**: {config.get('min_alloc_pct', 0.20):.0%}")
        st.markdown(f"- **Max allocation %**: {config.get('max_alloc_pct', 1.50):.0%}")
        st.markdown(f"- **Units**: {len(units)}")
        if scenario.params.excluded_floors:
            st.markdown(f"- **Excluded floors**: {', '.join(scenario.params.excluded_floors)}")
        if scenario.params.capacity_reduction_pct > 0:
            st.markdown(f"- **Capacity reduction**: {scenario.params.capacity_reduction_pct:.0%}")

    st.divider()

    # --- Run Optimization ---
    col1, col2 = st.columns([1, 3])
    with col1:
        run_opt = st.button("🚀 Run Optimization", type="primary", key="btn_run_opt")

    if run_opt:
        with st.spinner("Running optimization..."):
            result = optimize_allocation(
                allocations=scenario.allocation_results,
                floors=floors,
                baseline_assignments=scenario.floor_assignments,
                objective=selected_obj,
                excluded_floor_ids=scenario.params.excluded_floors,
                min_alloc_pct=config.get("min_alloc_pct", 0.20),
                max_alloc_pct=config.get("max_alloc_pct", 1.50),
                units=units,
            )

        # Store result in session state for display
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

        # Before/After comparison
        st.subheader("Before / After Comparison")
        if result.before_after:
            ba_df = pd.DataFrame(result.before_after)
            render_comparison_table(ba_df)

            # Impact summary
            helped = sum(1 for r in result.before_after if r["Seat Change"] > 0)
            impacted = sum(1 for r in result.before_after if r["Seat Change"] < 0)
            unchanged = sum(1 for r in result.before_after if r["Seat Change"] == 0)

            col1, col2, col3 = st.columns(3)
            col1.metric("Units Helped", helped)
            col2.metric("Units Impacted", impacted)
            col3.metric("Unchanged", unchanged)

        # Consolidation suggestions
        if result.consolidation_suggestions:
            st.subheader("Consolidation Suggestions")
            for s in result.consolidation_suggestions:
                st.info(s)

        # Accept button
        st.divider()
        if not scenario.is_locked:
            if st.button("✅ Accept & Apply to Scenario", type="primary", key="btn_accept_opt"):
                # Apply optimized assignments to scenario
                scenario.floor_assignments = result.assignments

                # Update allocated seats on allocation results
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
                st.session_state.pop("optimization_result", None)
                st.rerun()
        else:
            st.warning("Cannot apply — scenario is locked.")
