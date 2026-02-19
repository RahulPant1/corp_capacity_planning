"""Tab 5: Optimization & Recommendations — LP-based best-fit allocations."""

import streamlit as st
import pandas as pd
from datetime import datetime

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_rule_config,
    get_attendance,
    update_scenario, add_audit_entry, is_data_loaded,
)
from engine.optimizer import optimize_allocation
from engine.scenario_engine import apply_floor_modifications, apply_overrides
from components.tables import render_comparison_table
from config.defaults import PLANNING_BUFFER_PRESETS


def render(sidebar_state):
    """Render the Optimization & Recommendations tab."""
    st.header("Optimization & Recommendations")

    # --- How it works callout ---
    with st.expander("How does Optimization relate to Simulation?", expanded=False):
        st.markdown("""
**Simulation** (Scenario Lab) answers: *"How many seats does each unit need?"*
- Applies growth/attrition, allocation %, RTO mandate → computes per-unit demand

**Optimization** answers: *"Given those seat counts, where on which floors should each unit sit?"*
- Takes simulation demand as input → uses LP to decide floor placement
- Minimizes floors used, maximizes team cohesion (same/adjacent floors)
- RTO-Based and What-If modes can re-derive demand from attendance data

> **Important:** Run Simulation first. Re-run Simulation if scenario parameters change, then re-run Optimization.
        """)

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario or not scenario.allocation_results:
        st.info("No allocation results available. Run a simulation from the Scenario Lab first.")
        return

    if scenario.is_locked:
        st.warning(f"Scenario '{scenario.name}' is locked. Optimization results cannot be applied.")

    # --- Compute effective floors + attendance ---
    config = get_rule_config()
    raw_floors = get_floors()
    effective_floors = apply_floor_modifications(raw_floors, scenario)
    units = get_units()
    unit_names = [u.unit_name for u in units]
    tower_ids = sorted(set(f.tower_id for f in effective_floors))

    raw_total = sum(f.total_seats for f in raw_floors)
    effective_total = sum(f.total_seats for f in effective_floors)

    att_profiles = get_attendance()
    att_map_raw = {a.unit_name: a for a in att_profiles}
    _, scenario_att_map = apply_overrides(units, att_map_raw, scenario)

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

    target_rto = None
    if selected_obj == "rto_whatif":
        target_rto = st.slider(
            "Target RTO days/week for all units",
            min_value=1.0, max_value=5.0, value=3.0, step=0.5,
            key="opt_rto_target",
        )

    # --- Active Constraints (from scenario) ---
    with st.expander("Active Constraints (from Scenario)", expanded=False):
        if len(effective_floors) < len(raw_floors) or effective_total < raw_total:
            st.markdown(
                f"- **Floor capacity**: {len(raw_floors)} floors ({raw_total:,} seats) "
                f"→ **{len(effective_floors)} floors ({effective_total:,} seats)** after scenario adjustments"
            )
        else:
            st.markdown(f"- **Floor capacity**: {len(effective_floors)} floors, {effective_total:,} total seats")
        st.markdown(f"- **Global allocation %**: {config.get('global_alloc_pct', 0.80):.0%}")
        st.markdown(f"- **Demand cap**: each unit gets at most their simulation demand (respects allocation rule)")
        if scenario.params.excluded_floors:
            st.markdown(f"- **Excluded floors**: {', '.join(scenario.params.excluded_floors)}")
        if scenario.params.capacity_reduction_pct > 0:
            st.markdown(f"- **Capacity reduction**: {scenario.params.capacity_reduction_pct:.0%}")
        if selected_obj in ("rto_based", "rto_whatif"):
            st.markdown(f"- **Demand basis**: Attendance data (Median HC + Peak Buffer × RTO)")
            if selected_obj == "rto_whatif" and target_rto:
                st.markdown(f"- **Target RTO**: {target_rto} days/week for all units")

    # --- Advanced Runtime Constraints ---
    with st.expander("Advanced Constraints (optional, applied at run time)", expanded=False):
        st.caption("These constraints are applied on top of the objective. They may make the problem infeasible if too strict — the optimizer will warn you.")

        col1, col2 = st.columns(2)

        with col1:
            max_floors_enabled = st.checkbox("Limit max floors per unit", key="opt_maxfloors_on")
            max_floors_val = None
            if max_floors_enabled:
                max_floors_val = st.slider(
                    "Max floors per unit", min_value=1, max_value=5, value=2,
                    key="opt_maxfloors_val",
                    help="Each unit will be placed on at most this many floors, reducing fragmentation."
                )

        with col2:
            min_guar_enabled = st.checkbox("Minimum seats guarantee", key="opt_minguar_on")
            min_guar_val = None
            if min_guar_enabled:
                min_guar_val = st.slider(
                    "Min % of demand guaranteed per unit", min_value=50, max_value=100, value=80,
                    key="opt_minguar_val",
                    help="Each unit receives at least this % of their demand even under scarcity."
                ) / 100.0

        st.markdown("**Pin units to specific towers** (leave blank = no restriction)")
        pin_data = {}
        if tower_ids:
            pin_rows = []
            saved_pins = st.session_state.get("opt_pin_selections", {})
            for uname in unit_names:
                default = saved_pins.get(uname, tower_ids)
                selected = st.multiselect(
                    uname, options=tower_ids, default=default,
                    key=f"opt_pin_{uname}",
                    label_visibility="visible",
                )
                pin_data[uname] = selected if selected != tower_ids else None

        # Store pin selections
        st.session_state["opt_pin_selections"] = {
            uname: st.session_state.get(f"opt_pin_{uname}", tower_ids)
            for uname in unit_names
        }

    # Build pinned_tower_ids dict (only units with restrictions)
    pinned_tower_ids = {
        uname: towers
        for uname, towers in pin_data.items()
        if towers is not None and towers != tower_ids
    } or None

    st.divider()

    # --- Run Optimization ---
    col1, col2 = st.columns([1, 3])
    with col1:
        run_opt = st.button("Run Optimization", type="primary", key="btn_run_opt")
    with col2:
        run_sensitivity = st.button("Run Sensitivity Analysis", key="btn_sensitivity",
                                    help="Runs Lean/Balanced/Conservative buffer presets and compares seat demand range.")

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
                max_floors_per_unit=max_floors_val if max_floors_enabled else None,
                pinned_tower_ids=pinned_tower_ids,
                min_guarantee_pct=min_guar_val if min_guar_enabled else None,
            )

        # Store in history (last 3 runs)
        history = st.session_state.get("optimization_history", [])
        history.insert(0, {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "objective": objectives[selected_obj].split(" —")[0],
            "total_seats": sum(result.unit_allocations.values()),
            "floors_used": len(set((a.tower_id, a.floor_number) for a in result.assignments)),
            "status": result.status,
            "result": result,
        })
        st.session_state["optimization_history"] = history[:3]
        st.session_state["optimization_result"] = result

    if run_sensitivity:
        with st.spinner("Running sensitivity analysis (Lean / Balanced / Conservative)..."):
            sensitivity_rows = []
            alloc_total = sum(a.effective_demand_seats for a in scenario.allocation_results)
            for preset_name, preset_cfg in PLANNING_BUFFER_PRESETS.items():
                sens_config = dict(config)
                sens_config["peak_buffer_multiplier"] = preset_cfg["peak_buffer_multiplier"]
                r = optimize_allocation(
                    allocations=scenario.allocation_results,
                    floors=effective_floors,
                    baseline_assignments=scenario.floor_assignments,
                    objective=selected_obj,
                    excluded_floor_ids=[],
                    units=units,
                    attendance_map=scenario_att_map,
                    rule_config=sens_config,
                    target_rto_days=target_rto,
                )
                opt_seats = sum(r.unit_allocations.values())
                floors_used = len(set((a.tower_id, a.floor_number) for a in r.assignments))
                sensitivity_rows.append({
                    "Buffer Preset": preset_name.capitalize(),
                    "Peak Buffer Multiplier": preset_cfg["peak_buffer_multiplier"],
                    "Optimized Seats": opt_seats,
                    "Floors Used": floors_used,
                    "vs Allocation Rule": f"{opt_seats - alloc_total:+,}",
                })
            st.session_state["sensitivity_result"] = sensitivity_rows

    # --- Sensitivity Analysis Results ---
    if st.session_state.get("sensitivity_result"):
        st.divider()
        st.subheader("Sensitivity Analysis")
        st.caption("How seat needs vary across Lean / Balanced / Conservative planning buffer assumptions.")
        sens_df = pd.DataFrame(st.session_state["sensitivity_result"])
        st.dataframe(sens_df, use_container_width=True, hide_index=True)

    # --- Display Optimization Results ---
    result = st.session_state.get("optimization_result")
    if result:
        st.divider()
        st.subheader("Optimization Results")

        if "Optimal" in result.status:
            st.success(f"Status: {result.status}")
        else:
            st.error(f"Status: {result.status}")
            if result.message:
                st.warning(result.message)
            return

        if "relaxed" in result.message.lower():
            st.warning(result.message)
        else:
            st.info(result.message)

        # Savings summary (RTO objectives)
        if result.savings_summary:
            sv = result.savings_summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Allocation Rule Seats", f"{sv['allocation_rule_seats']:,}")
            col2.metric("RTO-Based Seats", f"{sv['rto_based_seats']:,}")
            col3.metric("Seats Saved", f"{sv['seats_saved']:,}",
                        delta=f"{sv['seats_saved']:+,}",
                        delta_color="normal" if sv['seats_saved'] >= 0 else "inverse")
            col4.metric("Floors Freed", sv['floors_freed'],
                        delta=f"{sv['floors_freed']:+d}",
                        delta_color="normal" if sv['floors_freed'] >= 0 else "inverse")

        # Before/After comparison
        st.subheader("Before / After Comparison")
        if result.before_after:
            ba_df = pd.DataFrame(result.before_after)
            render_comparison_table(ba_df)

            total_before = sum(r["Before Seats"] for r in result.before_after)
            total_after = sum(r["After Seats"] for r in result.before_after)
            total_floors_before = sum(r["Before Floors"] for r in result.before_after)
            total_floors_after = sum(r["After Floors"] for r in result.before_after)

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Seats", f"{total_after:,}", delta=f"{total_after - total_before:+,}")
            col2.metric("Total Floor Assignments", total_floors_after,
                        delta=f"{total_floors_after - total_floors_before:+d}")
            col3.metric("Units Consolidated",
                        sum(1 for r in result.before_after if r["Floor Change"] < 0))

        # --- Cost Estimation Panel ---
        st.subheader("Cost Estimation")
        cost_col1, cost_col2 = st.columns([1, 3])
        with cost_col1:
            cost_per_seat = st.number_input(
                "Cost per seat per year ($)",
                min_value=1000, max_value=50000, value=10000, step=1000,
                key="opt_cost_per_seat",
            )

        if result.unit_allocations and cost_per_seat:
            total_opt_seats = sum(result.unit_allocations.values())
            total_opt_cost = total_opt_seats * cost_per_seat

            col1, col2, col3 = st.columns(3)
            col1.metric("Optimized Seats", f"{total_opt_seats:,}")
            col2.metric("Annual Cost (Optimized)", f"${total_opt_cost:,.0f}")

            if result.savings_summary:
                savings_cost = result.savings_summary["seats_saved"] * cost_per_seat
                col3.metric("Annual Savings", f"${savings_cost:,.0f}",
                            delta=f"${savings_cost:+,.0f}",
                            delta_color="normal" if savings_cost >= 0 else "inverse")

            # Per-unit cost table
            with st.expander("Per-Unit Cost Breakdown", expanded=False):
                cost_rows = []
                for u, seats in sorted(result.unit_allocations.items()):
                    cost_rows.append({
                        "Unit": u,
                        "Optimized Seats": seats,
                        "Annual Cost": f"${seats * cost_per_seat:,.0f}",
                    })
                st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)

        # Consolidation suggestions
        if result.consolidation_suggestions:
            st.subheader("Consolidation Suggestions")
            for s in result.consolidation_suggestions:
                st.info(s)

        # --- Optimization History ---
        history = st.session_state.get("optimization_history", [])
        if len(history) > 1:
            st.subheader("Optimization History (Last 3 Runs)")
            hist_rows = [
                {
                    "Time": h["timestamp"],
                    "Objective": h["objective"],
                    "Total Seats": h["total_seats"],
                    "Floors Used": h["floors_used"],
                    "Status": h["status"],
                }
                for h in history
            ]
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

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
