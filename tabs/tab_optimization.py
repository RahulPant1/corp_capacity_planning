"""Tab 5: What-If Analysis — objective-first unified planning + optimization."""

import copy as _copy
import streamlit as st
import pandas as pd
from datetime import datetime

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_rule_config,
    get_attendance, get_cluster_map,
    update_scenario, add_audit_entry, is_data_loaded,
)
from engine.optimizer import optimize_allocation
from engine.scenario_engine import apply_floor_modifications, apply_overrides, run_scenario
from engine.scenario_comparison import run_scenario_matrix, rank_scenarios, get_best_scenario, build_explanation
from components.tables import render_comparison_table
from components.comparison_charts import scenario_demand_capacity_bar, scenario_metrics_heatmap
from config.defaults import (
    PLANNING_BUFFER_PRESETS,
    COMPARISON_MAX_COMBINATIONS,
    COMPARISON_ALLOC_OPTIONS,
    COMPARISON_RTO_OPTIONS,
    COMPARISON_CAPRED_OPTIONS,
    COMPARISON_OBJECTIVES,
    RISK_RED_GAP_PCT, RISK_AMBER_GAP_PCT,
    RISK_RED_FRAGMENTATION, RISK_AMBER_FRAGMENTATION,
)
from models.scenario import ScenarioParams, ScenarioOverride


def render(sidebar_state):
    """Render the What-If Analysis tab."""
    st.header("What-If Analysis")

    with st.expander("How does this work?", expanded=False):
        st.markdown("""
**Two planning flows in one tab:**

**1. Run Policy Simulation** — applies your unit-level overrides (growth %, alloc %) and reruns the policy allocation rules. Use this to set your baseline demand assumptions before optimising.

**2. Simulate & Optimize** — runs the LP optimizer on top of the policy simulation. Choose one of three modes:

| Mode | Demand basis | Alloc % used? | RTO slider |
|------|-------------|---------------|-----------|
| **Optimal Placement** | Headcount × Alloc % | ✅ Yes | ❌ Not used |
| **RTO-Based** | Actual attendance data | ❌ No | ❌ Not used |
| **What-If RTO** | Attendance × target RTO | ❌ No | Target RTO level |

Typical flow: set overrides → **Run Policy Simulation** → review demand → **Simulate & Optimize** → **Accept & Apply** → **Download Report**.
        """)

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario:
        st.info("No active scenario found. Load data in the Admin tab first.")
        return

    if not scenario.allocation_results:
        st.info(
            "No simulation run yet. Open **Unit-Level Overrides** below, set your assumptions, "
            "then click **Run Policy Simulation** to compute seat allocations."
        )

    if scenario.is_locked:
        st.warning(f"Scenario '{scenario.name}' is locked. Results cannot be applied.")

    # --- Setup ---
    config = get_rule_config()
    raw_floors = get_floors()
    effective_floors = apply_floor_modifications(raw_floors, scenario)
    units = get_units()
    unit_names = [u.unit_name for u in units]
    tower_ids = sorted(set(f.tower_id for f in effective_floors))

    effective_total = sum(f.total_seats for f in effective_floors)

    att_profiles = get_attendance()
    att_map_raw = {a.unit_name: a for a in att_profiles}
    _, scenario_att_map = apply_overrides(units, att_map_raw, scenario)

    rule_config_wi = get_rule_config()

    # =========================================================================
    # SECTION 1: Optimization Mode (drives which params are active below)
    # =========================================================================
    objectives = {
        "optimal_placement": "Optimal Placement — seat everyone per allocation rule on fewest floors",
        "rto_based": "RTO-Based — allocate by actual attendance patterns, free unused capacity",
        "rto_whatif": "What-If RTO — simulate a different RTO policy (e.g., 3 or 4 days/week)",
    }

    selected_obj = st.radio(
        "Optimization Mode",
        options=list(objectives.keys()),
        format_func=lambda k: objectives[k],
        key="opt_objective",
        horizontal=True,
    )

    # Contextual banner when sliders are disabled
    if selected_obj == "optimal_placement":
        st.info(
            "**Optimal Placement:** Demand is sized from Headcount × Alloc %. "
            "Global RTO Mandate is not used in this mode."
        )
    elif selected_obj == "rto_based":
        st.info(
            "**RTO-Based:** Demand is sized directly from attendance data — "
            "Global Alloc % and RTO Mandate are not used."
        )
    elif selected_obj == "rto_whatif":
        st.info(
            "**What-If RTO:** Simulates attendance at the target RTO level. "
            "Global Alloc % is not used — demand is attendance-driven."
        )

    # =========================================================================
    # SECTION 2: Planning Parameters (dynamically enabled/disabled by mode)
    # =========================================================================
    alloc_disabled = selected_obj in ("rto_based", "rto_whatif")
    rto_disabled = selected_obj in ("rto_based", "optimal_placement")
    rto_label = (
        "Target RTO (days/week)"
        if selected_obj == "rto_whatif"
        else "Global RTO Mandate (days/week)"
    )

    p1, p2, p3 = st.columns(3)
    with p1:
        wi_alloc_pct = st.slider(
            "Global Alloc %",
            min_value=50, max_value=150,
            value=int(rule_config_wi.get("global_alloc_pct", 0.80) * 100),
            step=5, format="%d%%",
            key="wi_alloc",
            disabled=alloc_disabled,
            help="Seats allocated as % of projected headcount. Drives seat demand (Optimal Placement only).",
        )
    with p2:
        wi_rto = st.slider(
            rto_label,
            min_value=0.5, max_value=5.0,
            value=float(scenario.params.global_rto_mandate_days or 3.0),
            step=0.5,
            key="wi_rto",
            disabled=rto_disabled,
            help=(
                "RTO mandate for simulation (Optimal Placement) or "
                "target RTO level for the optimizer (What-If RTO)."
            ),
        )
    with p3:
        wi_cap_red_pct = st.slider(
            "Floor Capacity Reduction (%)",
            min_value=0, max_value=15,
            value=max(0, int((scenario.params.capacity_reduction_pct or 0.0) * 100)),
            step=1, format="%d%%",
            key="wi_capred",
            help="Reduces usable seats on every floor by this % (e.g. distancing buffer, hot-desk ratio). Applies to all modes.",
        )

    # Excluded floors multiselect
    all_floor_ids = sorted(set(f.floor_id for f in raw_floors))
    valid_excluded = [f for f in (scenario.params.excluded_floors or []) if f in all_floor_ids]
    wi_excluded_floors = st.multiselect(
        "Floors to Exclude from Planning",
        options=all_floor_ids,
        default=valid_excluded,
        key="wi_excluded_floors",
        help="Remove specific floors from available supply — e.g. renovation, sublease, or decommission. "
             "Applies to both Policy Simulation and Simulate & Optimize.",
    )

    # =========================================================================
    # SECTION 3: Placement Controls
    # =========================================================================
    st.markdown("**Placement Controls**")
    st.caption(
        "Applied on top of the optimization objective. "
        "Relaxed automatically if they make the problem infeasible."
    )
    qc1, qc2 = st.columns(2)
    with qc1:
        max_floors_val = st.slider(
            "Max floors per unit",
            min_value=1, max_value=5, value=3,
            key="opt_maxfloors_val",
            help="Limits how many floors each unit can occupy. Lower = more consolidated.",
        )
    with qc2:
        min_guar_val = st.slider(
            "Minimum seat guarantee (% of demand)",
            min_value=50, max_value=100, value=80,
            key="opt_minguar_val",
            help="Each unit is guaranteed at least this % of their demand, even under scarcity.",
        ) / 100.0

    # =========================================================================
    # SECTION 4: Advanced Tower Restrictions
    # =========================================================================
    with st.expander("Advanced: Unit Tower Restrictions", expanded=False):
        st.caption("Pin specific units to certain towers. Leave all towers selected = no restriction.")
        pin_data = {}
        if tower_ids:
            saved_pins = st.session_state.get("opt_pin_selections", {})
            for uname in unit_names:
                saved = saved_pins.get(uname, tower_ids)
                default = [t for t in saved if t in tower_ids] or tower_ids
                selected = st.multiselect(
                    uname, options=tower_ids, default=default,
                    key=f"opt_pin_{uname}",
                    label_visibility="visible",
                )
                pin_data[uname] = selected if selected != tower_ids else None

        st.session_state["opt_pin_selections"] = {
            uname: st.session_state.get(f"opt_pin_{uname}", tower_ids)
            for uname in unit_names
        }

    pinned_tower_ids = {
        uname: towers
        for uname, towers in pin_data.items()
        if towers is not None and towers != tower_ids
    } or None

    # =========================================================================
    # SECTION 4.5: Per-Unit Overrides
    # =========================================================================
    with st.expander("Unit-Level Overrides", expanded=False):
        st.caption(
            "Override HC growth % or pin a specific allocation % per unit. "
            "Applied by **Run Policy Simulation** and carried into **Simulate & Optimize**."
        )
        att_profiles_ov = get_attendance()
        att_map_ov = {a.unit_name: a for a in att_profiles_ov}
        override_rows = []
        for u in units:
            ov = scenario.unit_overrides.get(u.unit_name, ScenarioOverride(unit_name=u.unit_name))
            override_rows.append({
                "Unit": u.unit_name,
                "HC Growth %": round(
                    (ov.hc_growth_pct if ov.hc_growth_pct is not None else u.hc_growth_pct) * 100, 1
                ),
                "Alloc % Override (0 = use policy)": round((ov.alloc_pct_override or 0) * 100, 1),
            })
        edited_overrides = st.data_editor(
            pd.DataFrame(override_rows),
            disabled=["Unit"],
            use_container_width=True,
            key="opt_unit_overrides_editor",
            num_rows="fixed",
        )
        if st.button("Clear All Overrides", key="btn_clear_overrides"):
            scenario.unit_overrides = {}
            update_scenario(scenario)
            add_audit_entry("clear_overrides", scenario.scenario_id, "unit_overrides", "overrides", "cleared")
            st.success("All overrides cleared.")
            st.rerun()

    # =========================================================================
    # SECTION 2.5: Additional Planning Inputs
    # =========================================================================
    st.markdown("**Additional Planning Inputs**")
    cluster_map_wi = get_cluster_map()
    use_cluster_diversity = False
    if cluster_map_wi:
        use_cluster_diversity = st.checkbox(
            "Cluster-Diverse Floor Placement",
            value=False,
            key="wi_cluster_diversity",
            help=(
                "Prefer placing units from different attendance clusters on the same floor, "
                "reducing peak-day saturation risk. "
                "Units in the same cluster peak on the same days — spreading them across floors "
                "reduces saturation. Clusters are computed in Demand Analytics."
            ),
        )
        if use_cluster_diversity:
            from collections import Counter as _Counter
            _cid_counts = _Counter(cluster_map_wi.values())
            _grp_summary = " · ".join(
                f"Group {cid + 1}: {cnt} unit{'s' if cnt != 1 else ''}"
                for cid, cnt in sorted(_cid_counts.items())
            )
            st.caption(f"Cluster data available — {_grp_summary}")
    else:
        st.caption(
            "ℹ️ Cluster-Diverse Placement unavailable — "
            "compute Temporal Clusters in Demand Analytics (or load sample data from Admin) first."
        )

    # Active scenario summary caption
    active_items = []
    if wi_excluded_floors:
        active_items.append(f"{len(wi_excluded_floors)} floor(s) excluded")
    if wi_cap_red_pct:
        active_items.append(f"capacity reduced {wi_cap_red_pct}%")
    if use_cluster_diversity:
        active_items.append("cluster-diverse placement ON")
    if active_items:
        st.caption("Planning with: " + " · ".join(active_items))

    st.divider()

    # =========================================================================
    # SECTION 5: Run Buttons
    # =========================================================================
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        run_policy = st.button(
            "Run Policy Simulation", key="btn_run_policy",
            help="Apply overrides and recompute allocation using policy rules only (no LP optimizer).",
        )
    with col2:
        run_main = st.button("Simulate & Optimize", type="primary", key="btn_run_main")
    with col3:
        run_sensitivity = st.button(
            "Run Sensitivity Analysis", key="btn_sensitivity",
            help="Runs Lean/Balanced/Conservative buffer presets and compares seat demand range.",
        )

    # =========================================================================
    # SECTION 6: Handlers
    # =========================================================================
    if run_policy:
        with st.spinner("Running policy simulation..."):
            _base_units = get_units()
            _att_map_ps = {a.unit_name: a for a in get_attendance()}
            _overrides_ps = {}
            for _, row in edited_overrides.iterrows():
                _uname = row["Unit"]
                _bu = next((u for u in _base_units if u.unit_name == _uname), None)
                if not _bu:
                    continue
                _ov = ScenarioOverride(unit_name=_uname)
                _changed = False
                if abs(row["HC Growth %"] - _bu.hc_growth_pct * 100) > 0.01:
                    _ov.hc_growth_pct = row["HC Growth %"] / 100.0
                    _changed = True
                if row["Alloc % Override (0 = use policy)"] > 0:
                    _ov.alloc_pct_override = row["Alloc % Override (0 = use policy)"] / 100.0
                    _changed = True
                if _changed:
                    _overrides_ps[_uname] = _ov
            scenario.unit_overrides = _overrides_ps
            scenario.params = ScenarioParams(
                global_rto_mandate_days=wi_rto,
                capacity_reduction_pct=wi_cap_red_pct / 100.0,
                excluded_floors=wi_excluded_floors,
            )
            _rc_ps = dict(get_rule_config())
            if use_cluster_diversity and cluster_map_wi:
                _rc_ps["cluster_map"] = cluster_map_wi
            if pinned_tower_ids:
                _rc_ps["tower_restrictions"] = pinned_tower_ids
            scenario = run_scenario(scenario, _base_units, _att_map_ps, raw_floors, _rc_ps)
            update_scenario(scenario)
            add_audit_entry(
                "policy_simulation", scenario.scenario_id,
                "all", "", f"Policy sim with {len(_overrides_ps)} override(s)",
            )
        st.session_state["policy_sim_ran"] = True
        st.success(f"Policy simulation complete — {len(_overrides_ps)} unit override(s) applied.")
        st.rerun()

    if run_main:
        with st.spinner("Simulating scenario then optimizing floor placement..."):
            rc_combined = dict(rule_config_wi)

            # Build mode-specific params
            if selected_obj == "optimal_placement":
                rc_combined["global_alloc_pct"] = wi_alloc_pct / 100.0
                rto_mandate_val = None
                target_rto_for_opt = None
            elif selected_obj == "rto_whatif":
                rc_combined["global_alloc_pct"] = config.get("global_alloc_pct", 0.80)
                rto_mandate_val = None
                target_rto_for_opt = wi_rto
            else:  # rto_based
                rc_combined["global_alloc_pct"] = config.get("global_alloc_pct", 0.80)
                rto_mandate_val = None
                target_rto_for_opt = None

            # Build temp scenario with what-if params
            temp_scenario = _copy.deepcopy(scenario)
            temp_scenario.params = ScenarioParams(
                global_rto_mandate_days=rto_mandate_val,
                capacity_reduction_pct=wi_cap_red_pct / 100.0,
                excluded_floors=wi_excluded_floors,
            )

            # Inject cluster diversity into run_scenario (greedy spatial path)
            if use_cluster_diversity and cluster_map_wi:
                rc_combined["cluster_map"] = cluster_map_wi

            # Re-run simulation with updated demand params
            temp_scenario = run_scenario(temp_scenario, units, att_map_raw, raw_floors, rc_combined)
            temp_eff_floors = apply_floor_modifications(raw_floors, temp_scenario)
            _, temp_att_map = apply_overrides(units, att_map_raw, temp_scenario)

            # Run LP optimizer
            result = optimize_allocation(
                allocations=temp_scenario.allocation_results,
                floors=temp_eff_floors,
                baseline_assignments=scenario.floor_assignments,
                objective=selected_obj,
                excluded_floor_ids=[],
                units=units,
                attendance_map=temp_att_map,
                rule_config=rc_combined,
                target_rto_days=target_rto_for_opt,
                max_floors_per_unit=max_floors_val,
                pinned_tower_ids=pinned_tower_ids,
                min_guarantee_pct=min_guar_val,
            )

        # Store results + params used (for Accept & Apply)
        st.session_state["optimization_result"] = result
        st.session_state["last_sim_scenario"] = temp_scenario
        st.session_state["last_run_params"] = {
            "objective": selected_obj,
            "alloc_pct": rc_combined["global_alloc_pct"],
            "rto_mandate": rto_mandate_val,
            "cap_red": wi_cap_red_pct / 100.0,
        }

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

    if run_sensitivity and not scenario.allocation_results:
        st.warning("Run a Policy Simulation first before running Sensitivity Analysis.")
    if run_sensitivity and scenario.allocation_results:
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
                    target_rto_days=None,
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

    # =========================================================================
    # SECTION 7: Sensitivity Results
    # =========================================================================
    if st.session_state.get("sensitivity_result"):
        st.divider()
        st.subheader("Sensitivity Analysis")
        st.caption("How seat needs vary across Lean / Balanced / Conservative planning buffer assumptions.")
        sens_df = pd.DataFrame(st.session_state["sensitivity_result"])
        st.dataframe(sens_df, use_container_width=True, hide_index=True)

    # =========================================================================
    # SECTION 7.5: Policy Simulation Results
    # =========================================================================
    if st.session_state.get("policy_sim_ran") and scenario.allocation_results:
        st.divider()
        st.subheader("Policy Simulation Results")
        st.caption("Allocation based on policy rules + unit overrides. No LP optimizer applied.")

        _ps_allocs = scenario.allocation_results
        _ps_demand = sum(a.effective_demand_seats for a in _ps_allocs)
        _ps_alloc = sum(a.allocated_seats for a in _ps_allocs)
        _ps_gap = _ps_alloc - _ps_demand
        _ps_risk = sum(
            1 for a in _ps_allocs
            if (a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0)
            < RISK_AMBER_GAP_PCT
        )
        ps1, ps2, ps3, ps4 = st.columns(4)
        ps1.metric("Total Demand", f"{_ps_demand:,}")
        ps2.metric("Total Allocated", f"{_ps_alloc:,}")
        ps3.metric("Net Gap", f"{_ps_gap:+,}",
                   delta_color="normal" if _ps_gap >= 0 else "inverse")
        ps4.metric("Units at Risk", str(_ps_risk),
                   delta_color="inverse" if _ps_risk > 0 else "normal")

        # Cluster diversity metric (only when cluster data is available)
        if cluster_map_wi and scenario.floor_assignments:
            from collections import defaultdict as _defaultdict
            _floor_clusters: dict = _defaultdict(set)
            for _fa in scenario.floor_assignments:
                _cid = cluster_map_wi.get(_fa.unit_name)
                if _cid is not None:
                    _floor_clusters[f"{_fa.tower_id} F{_fa.floor_number}"].add(_cid)
            if _floor_clusters:
                _avg_div = sum(len(v) for v in _floor_clusters.values()) / len(_floor_clusters)
                st.metric(
                    "Avg Attendance Groups / Floor",
                    f"{_avg_div:.1f}",
                    help=(
                        "Average number of distinct attendance clusters across assigned floors. "
                        "Higher = better peak diversification. "
                        "Enable Cluster-Diverse Placement to increase this."
                    ),
                )

        _ps_rows = []
        for a in _ps_allocs:
            _ps_rows.append({
                "Unit": a.unit_name,
                "Policy Alloc %": f"{a.recommended_alloc_pct:.1%}",
                "Policy Demand": a.effective_demand_seats,
                "Allocated Seats": a.allocated_seats,
                "Gap (vs Policy)": a.seat_gap,
                "Fragmentation": f"{a.fragmentation_score:.2f}",
                "Overridden": "Yes" if a.is_overridden else "",
            })
        st.dataframe(pd.DataFrame(_ps_rows), use_container_width=True, hide_index=True)

        _ps_risks = []
        for a in _ps_allocs:
            _gp = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
            if _gp < RISK_RED_GAP_PCT or a.fragmentation_score > RISK_RED_FRAGMENTATION:
                _ps_risks.append((a.unit_name, "RED", _gp, a.fragmentation_score))
            elif _gp < RISK_AMBER_GAP_PCT or a.fragmentation_score > RISK_AMBER_FRAGMENTATION:
                _ps_risks.append((a.unit_name, "AMBER", _gp, a.fragmentation_score))
        if _ps_risks:
            st.markdown("**Key Risks:**")
            for _name, _lvl, _gp, _frag in _ps_risks:
                _parts = []
                if _gp < RISK_AMBER_GAP_PCT:
                    _parts.append(f"seat shortfall {_gp:.0%}")
                if _frag > RISK_AMBER_FRAGMENTATION:
                    _parts.append(f"high fragmentation {_frag:.2f}")
                st.markdown(
                    f"- :{'red' if _lvl == 'RED' else 'orange'}[{_lvl}] **{_name}** — {', '.join(_parts)}"
                )

    # =========================================================================
    # SECTION 8: Combined Results Panel
    # =========================================================================
    result = st.session_state.get("optimization_result")
    last_sim = st.session_state.get("last_sim_scenario")

    if result:
        st.divider()
        st.subheader("Results")

        # --- Planning Impact metrics (demand + capacity delta vs baseline) ---
        if last_sim:
            baseline_demand = sum(a.effective_demand_seats for a in scenario.allocation_results)
            new_demand = sum(a.effective_demand_seats for a in last_sim.allocation_results)
            new_eff_floors = apply_floor_modifications(raw_floors, last_sim)
            new_cap = sum(f.total_seats for f in new_eff_floors)
            demand_delta = new_demand - baseline_demand
            cap_delta = new_cap - effective_total
            headroom = new_cap - new_demand

            if demand_delta != 0 or cap_delta != 0:
                st.markdown("**Planning Impact** (vs current baseline)")
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "Seat Demand", f"{new_demand:,}",
                    delta=f"{demand_delta:+,}" if demand_delta != 0 else None,
                    delta_color="inverse",
                )
                m2.metric(
                    "Available Capacity", f"{new_cap:,}",
                    delta=f"{cap_delta:+,}" if cap_delta != 0 else None,
                    delta_color="off",
                )
                m3.metric("Headroom", f"{headroom:+,} seats")

                if headroom < 0:
                    st.warning(
                        f"Capacity shortfall: demand exceeds capacity by **{abs(headroom):,} seats**."
                    )
                elif cap_delta < 0 and demand_delta == 0:
                    st.info(
                        f"Capacity reduced by **{abs(cap_delta):,} seats** but demand is still met "
                        f"— headroom shrinks from {effective_total - baseline_demand:,} to "
                        f"**{headroom:,} seats**."
                    )

        # --- Optimization Status ---
        if "Optimal" in result.status:
            st.success(f"Status: {result.status}")
        else:
            st.error(f"Status: {result.status}")
            if result.message:
                st.warning(result.message)
            return

        if result.message:
            if "relaxed" in result.message.lower():
                st.warning(result.message)
            else:
                st.info(result.message)

        # --- Savings summary (RTO objectives) ---
        if result.savings_summary:
            sv = result.savings_summary
            sv1, sv2, sv3, sv4 = st.columns(4)
            sv1.metric("Policy-Based Seats (80% Rule)", f"{sv['allocation_rule_seats']:,}")
            sv2.metric("Attendance-Based Seats", f"{sv['rto_based_seats']:,}")
            sv3.metric("Seats Saved", f"{sv['seats_saved']:,}",
                       delta=f"{sv['seats_saved']:+,}",
                       delta_color="normal" if sv["seats_saved"] >= 0 else "inverse")
            sv4.metric("Floors Freed", sv["floors_freed"],
                       delta=f"{sv['floors_freed']:+d}",
                       delta_color="normal" if sv["floors_freed"] >= 0 else "inverse")

        # --- Before / After Comparison ---
        st.subheader("Before / After Comparison")
        st.caption(
            "Per-unit seat count before (policy rule) and after (optimization). "
            "Green = seats freed, Red = seats added."
        )
        if result.before_after:
            ba_df = pd.DataFrame(result.before_after)
            render_comparison_table(ba_df)

            cross_bldg_units = [
                row["Unit"] for row in result.before_after
                if row.get("Buildings After", 1) > 1
            ]
            if cross_bldg_units:
                st.warning(
                    f"⚠️ **Cross-building placement:** {', '.join(cross_bldg_units)} "
                    f"{'are' if len(cross_bldg_units) > 1 else 'is'} split across buildings. "
                    "This happens when a single building lacks sufficient capacity. "
                    "To consolidate: increase Max Floors Per Unit, remove tower pins, "
                    "or check if excluded floors are limiting available supply."
                )

            total_before = sum(r["Before Seats"] for r in result.before_after)
            total_after = sum(r["After Seats"] for r in result.before_after)
            total_floors_before = sum(r["Before Floors"] for r in result.before_after)
            total_floors_after = sum(r["After Floors"] for r in result.before_after)

            s1, s2, s3 = st.columns(3)
            s1.metric("Total Seats", f"{total_after:,}", delta=f"{total_after - total_before:+,}")
            s2.metric("Total Floor Assignments", total_floors_after,
                      delta=f"{total_floors_after - total_floors_before:+d}")
            s3.metric("Units Consolidated",
                      sum(1 for r in result.before_after if r["Floor Change"] < 0))

        # --- Cost Estimation ---
        with st.expander("Cost Estimation", expanded=False):
            cost_col1, _ = st.columns([1, 3])
            with cost_col1:
                cost_per_seat = st.number_input(
                    "Cost per seat per year ($)",
                    min_value=1000, max_value=50000, value=10000, step=1000,
                    key="opt_cost_per_seat",
                )
            if result.unit_allocations and cost_per_seat:
                total_opt_seats = sum(result.unit_allocations.values())
                total_opt_cost = total_opt_seats * cost_per_seat
                ce1, ce2, ce3 = st.columns(3)
                ce1.metric("Optimized Seats", f"{total_opt_seats:,}")
                ce2.metric("Annual Cost (Optimized)", f"${total_opt_cost:,.0f}")
                if result.savings_summary:
                    savings_cost = result.savings_summary["seats_saved"] * cost_per_seat
                    ce3.metric("Annual Savings", f"${savings_cost:,.0f}",
                               delta=f"${savings_cost:+,.0f}",
                               delta_color="normal" if savings_cost >= 0 else "inverse")

                with st.expander("Per-Unit Cost Breakdown", expanded=False):
                    cost_rows = [
                        {
                            "Unit": u,
                            "Optimized Seats": seats,
                            "Annual Cost": f"${seats * cost_per_seat:,.0f}",
                        }
                        for u, seats in sorted(result.unit_allocations.items())
                    ]
                    st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)

        # --- Consolidation Suggestions ---
        if result.consolidation_suggestions:
            st.subheader("Consolidation Suggestions")
            for s in result.consolidation_suggestions:
                st.info(s)

        # --- Optimization History ---
        history = st.session_state.get("optimization_history", [])
        if len(history) > 1:
            with st.expander("Optimization History (Last 3 Runs)", expanded=False):
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

        # --- Accept & Apply (commits demand params + floor assignments together) ---
        st.divider()
        if not scenario.is_locked:
            lrp = st.session_state.get("last_run_params", {})
            obj_label = objectives.get(lrp.get("objective", selected_obj), "").split(" —")[0]
            st.caption(
                f"Last run: **{obj_label}** · "
                f"Alloc {lrp.get('alloc_pct', config.get('global_alloc_pct', 0.80)):.0%} · "
                f"Cap reduction {lrp.get('cap_red', 0.0):.0%}"
                + (f" · RTO {lrp['rto_mandate']}d/wk" if lrp.get("rto_mandate") else "")
            )
            if st.button("Accept & Apply to Scenario", type="primary", key="btn_accept_opt"):
                # Apply planning demand params
                rc = dict(config)
                rc["global_alloc_pct"] = lrp.get("alloc_pct", config.get("global_alloc_pct", 0.80))
                st.session_state["rule_config"] = rc
                scenario.params = ScenarioParams(
                    global_rto_mandate_days=lrp.get("rto_mandate"),
                    capacity_reduction_pct=lrp.get("cap_red", 0.0),
                    excluded_floors=scenario.params.excluded_floors,
                    optimizer_objective=lrp.get("objective", selected_obj),
                    max_floors_per_unit=max_floors_val if max_floors_val != 3 else None,
                    pinned_tower_ids=pinned_tower_ids if pinned_tower_ids else None,
                )
                # Apply floor assignments from optimizer
                scenario.floor_assignments = result.assignments
                for alloc in scenario.allocation_results:
                    alloc.allocated_seats = result.unit_allocations.get(alloc.unit_name, 0)
                    alloc.seat_gap = alloc.allocated_seats - alloc.effective_demand_seats
                # Re-run scenario so all tabs see updated demand (recalculates effective_demand_seats with new params)
                scenario = run_scenario(scenario, units, att_map_raw, raw_floors, rc)
                # Restore optimizer floor assignments — run_scenario overwrites with unconstrained spatial re-assignment
                scenario.floor_assignments = result.assignments
                # Restore optimizer seat counts — run_scenario overwrites allocated_seats with policy-based values
                for _alloc in scenario.allocation_results:
                    if _alloc.unit_name in result.unit_allocations:
                        _alloc.allocated_seats = result.unit_allocations[_alloc.unit_name]
                        _alloc.seat_gap = _alloc.allocated_seats - _alloc.effective_demand_seats
                update_scenario(scenario)
                add_audit_entry(
                    "accept_optimization", scenario.scenario_id,
                    "floor_assignments", "rule-based",
                    f"optimized ({lrp.get('objective', selected_obj)})",
                    rationale=(
                        f"Accepted {lrp.get('objective', selected_obj)} optimization. "
                        f"Alloc {rc['global_alloc_pct']:.0%}, "
                        f"cap red {lrp.get('cap_red', 0.0):.0%}"
                    ),
                )
                st.success(
                    "Scenario updated — demand params and floor assignments applied. "
                    "Dashboard, Spatial View, and Unit Impact now reflect the changes."
                )
                st.session_state.pop("optimization_result", None)
                st.session_state.pop("last_sim_scenario", None)
                st.session_state.pop("last_run_params", None)
                st.rerun()
        else:
            st.warning("Cannot apply — scenario is locked.")

    # =========================================================================
    # SECTION 8.5: Download Report
    # =========================================================================
    if scenario.allocation_results:
        with st.expander("Download Report", expanded=False):
            from datetime import date as _date
            from engine.report_generator import generate_scenario_report
            from engine.pdf_report_generator import generate_pdf_report
            from data.session_store import get_daily_attendance_df

            _daily_df = get_daily_attendance_df()
            _matrix = st.session_state.get("cmp_matrix_results")
            _opt_hist = st.session_state.get("optimization_history", [])
            _att_rpt = {a.unit_name: a for a in get_attendance()}

            _included = ["allocation results", "floor assignments", "risks"]
            if _opt_hist:
                _included.append("optimization run")
            if _daily_df is not None:
                _included.append("demand forecast")
            if _matrix:
                _included.append(f"scenario comparison ({len(_matrix)} runs)")
            st.caption("Export includes: " + ", ".join(_included) + ".")

            _report_bytes = generate_scenario_report(
                scenario=scenario,
                floors=raw_floors,
                units=units,
                attendance_map=_att_rpt,
                rule_config=get_rule_config(),
                opt_history=_opt_hist if _opt_hist else None,
                daily_attendance_df=_daily_df,
                matrix_results=_matrix,
            )
            st.download_button(
                label="Download Scenario Report (.xlsx)",
                data=_report_bytes,
                file_name=f"scenario_{scenario.name.replace(' ', '_')}_{_date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_whatif_dl_xlsx",
            )

            _pdf_bytes = generate_pdf_report(
                scenario=scenario,
                floors=raw_floors,
                units=units,
                attendance_map=_att_rpt,
                rule_config=get_rule_config(),
                opt_history=_opt_hist if _opt_hist else None,
                daily_attendance_df=_daily_df,
                matrix_results=_matrix,
            )
            st.download_button(
                label="Download Boardroom Report (.pdf)",
                data=_pdf_bytes,
                file_name=f"scenario_{scenario.name.replace(' ', '_')}_{_date.today()}.pdf",
                mime="application/pdf",
                key="btn_whatif_dl_pdf",
            )

    st.divider()

    # =========================================================================
    # SECTION 9: Scenario Comparison Matrix
    # =========================================================================
    with st.expander("Scenario Comparison Matrix", expanded=False):
        st.markdown(
            "Automatically run **multiple parameter combinations** and compare results side-by-side. "
            "Select the values you want to test for each parameter — the tool will run every combination "
            "and rank them by composite score (headroom, gap, fragmentation, consolidation)."
        )
        st.caption(
            f"Maximum {COMPARISON_MAX_COMBINATIONS} combinations. "
            "Placement controls (Max Floors, Min Guarantee) from the sliders above are applied to all runs."
        )

        # ── Parameter selection ──────────────────────────────────────
        st.markdown("**Step 1: Select parameter values to test**")

        cmp_c1, cmp_c2 = st.columns(2)
        with cmp_c1:
            use_alloc = st.checkbox("Vary Global Alloc %", value=True, key="cmp_use_alloc")
            if use_alloc:
                cmp_alloc_vals = st.multiselect(
                    "Alloc % values",
                    options=COMPARISON_ALLOC_OPTIONS,
                    default=[0.70, 0.80, 0.90],
                    format_func=lambda x: f"{x:.0%}",
                    key="cmp_alloc_vals",
                )
            else:
                cmp_alloc_vals = [rule_config_wi.get("global_alloc_pct", 0.80)]

            use_rto = st.checkbox("Vary RTO Mandate", value=False, key="cmp_use_rto")
            if use_rto:
                cmp_rto_vals = st.multiselect(
                    "RTO values (days/week)",
                    options=COMPARISON_RTO_OPTIONS,
                    default=[2.0, 3.0, 4.0],
                    format_func=lambda x: f"{x:.1f}d/wk",
                    key="cmp_rto_vals",
                )
            else:
                cmp_rto_vals = [float(scenario.params.global_rto_mandate_days or 3.0)]

        with cmp_c2:
            use_capred = st.checkbox("Vary Capacity Reduction %", value=False, key="cmp_use_capred")
            if use_capred:
                cmp_capred_vals = st.multiselect(
                    "Capacity Reduction values",
                    options=COMPARISON_CAPRED_OPTIONS,
                    default=[0.0, 0.10],
                    format_func=lambda x: f"{x:.0%}",
                    key="cmp_capred_vals",
                )
            else:
                cmp_capred_vals = [float(scenario.params.capacity_reduction_pct or 0.0)]

            use_obj = st.checkbox("Vary Optimization Mode", value=True, key="cmp_use_obj")
            if use_obj:
                obj_display = {
                    "optimal_placement": "Optimal Placement",
                    "rto_based": "RTO-Based",
                }
                cmp_obj_vals = st.multiselect(
                    "Optimization modes",
                    options=COMPARISON_OBJECTIVES,
                    default=["optimal_placement"],
                    format_func=lambda x: obj_display.get(x, x),
                    key="cmp_obj_vals",
                )
            else:
                cmp_obj_vals = ["optimal_placement"]

        # Guard: non-empty selections
        cmp_alloc_vals = cmp_alloc_vals or [rule_config_wi.get("global_alloc_pct", 0.80)]
        cmp_rto_vals   = cmp_rto_vals   or [float(scenario.params.global_rto_mandate_days or 3.0)]
        cmp_capred_vals = cmp_capred_vals or [0.0]
        cmp_obj_vals   = cmp_obj_vals   or ["optimal_placement"]

        n_combos = len(cmp_alloc_vals) * len(cmp_rto_vals) * len(cmp_capred_vals) * len(cmp_obj_vals)
        if n_combos > COMPARISON_MAX_COMBINATIONS:
            st.warning(
                f"**{n_combos} combinations** exceeds the limit of {COMPARISON_MAX_COMBINATIONS}. "
                "Please reduce the number of values selected."
            )
            run_matrix = False
        else:
            st.info(f"**{n_combos} combination{'s' if n_combos != 1 else ''}** will be run.")

            # Parameter interaction guidance
            _guidance = []
            if use_rto and use_capred:
                _guidance.append(
                    "**Capacity Reduction** shrinks physical seat *supply* (floor seats × (1 − cap_red%)). "
                    "**RTO Mandate** raises the in-office attendance floor, affecting projected *demand*. "
                    "These are independent dimensions — both apply simultaneously when non-zero. "
                    "If your teams already attend at or above the mandate, varying RTO will not change demand outcomes."
                )
            if use_rto and "rto_based" in cmp_obj_vals:
                _guidance.append(
                    "**RTO-Based optimization** mode derives seat needs directly from attendance — it ignores Alloc %. "
                    "Alloc % variations produce the same results in RTO-Based mode (shown as N/A in the table)."
                )
            if _guidance:
                with st.expander("ℹ️ Parameter interaction notes", expanded=True):
                    for note in _guidance:
                        st.caption(note)

            run_matrix = st.button(
                f"Run All {n_combos} Scenarios", type="primary", key="btn_run_matrix",
            )

        # ── Run matrix ───────────────────────────────────────────────
        if run_matrix:
            param_grid = {
                "alloc_pct":   cmp_alloc_vals,
                "rto_mandate": cmp_rto_vals,
                "cap_red":     cmp_capred_vals,
                "objective":   cmp_obj_vals,
            }
            progress_bar = st.progress(0, text="Running scenarios…")
            with st.spinner(f"Running {n_combos} scenario combinations…"):
                raw_results = run_scenario_matrix(
                    base_scenario=scenario,
                    units=units,
                    attendance_map=att_map_raw,
                    floors=raw_floors,
                    rule_config=rule_config_wi,
                    param_grid=param_grid,
                    max_floors_per_unit=max_floors_val,
                    min_guarantee_pct=min_guar_val,
                )
                ranked = rank_scenarios(raw_results)
            progress_bar.progress(1.0, text="Done.")
            st.session_state["cmp_matrix_results"] = ranked

        # ── Results ──────────────────────────────────────────────────
        ranked_results = st.session_state.get("cmp_matrix_results")
        if ranked_results:
            st.markdown("---")
            st.markdown("**Step 2: Comparison Report**")

            best = get_best_scenario(ranked_results)
            if best and not best["opt_status"].startswith("Error"):
                obj_label = {
                    "optimal_placement": "Optimal Placement",
                    "rto_based": "RTO-Based",
                    "rto_whatif": "What-If RTO",
                }.get(best["objective"], best["objective"])
                alloc_str = f"Alloc {best['alloc_pct']:.0%}, " if best["alloc_pct"] is not None else ""
                st.success(
                    f"**Best Scenario #{best['rank']}:** "
                    f"{alloc_str}RTO {best['rto_mandate']:.1f}d/wk, "
                    f"Cap Red {best['cap_red']:.0%}, {obj_label}  \n"
                    f"{build_explanation(best)}"
                )

            # Summary table
            display_rows = []
            for r in ranked_results:
                display_rows.append({
                    "Rank": r["rank"],
                    "Alloc %": f"{r['alloc_pct']:.0%}" if r["alloc_pct"] is not None else "N/A",
                    "RTO": f"{r['rto_mandate']:.1f}d",
                    "Cap Red": f"{r['cap_red']:.0%}",
                    "Mode": {"optimal_placement": "Optimal", "rto_based": "RTO", "rto_whatif": "WI"}.get(r["objective"], r["objective"]),
                    "RTO Active?": "Yes" if r.get("rto_binding") else "No",
                    "Demand": f"{r['demand']:,}",
                    "Capacity": f"{r['capacity']:,}",
                    "Headroom": f"{r['headroom']:+,}",
                    "Gap": f"{r['total_gap']:+,}",
                    "Units at Risk": r["units_at_risk"],
                    "Opt Seats": f"{r['opt_seats']:,}",
                    "Floors Used": r["floors_used"],
                    "Avg Frag": f"{r['avg_fragmentation']:.2f}",
                    "Seats Saved": f"{r['seats_saved']:,}",
                    "Status": r["opt_status"],
                    "Score": f"{r.get('composite_score', 0):.3f}",
                })
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

            # Redundancy detection: flag RTO combinations where demand is identical despite different RTO values
            _rdf = pd.DataFrame([{
                "alloc": r.get("alloc_pct"), "cap": r.get("cap_red"),
                "obj": r.get("objective"), "rto": r.get("rto_mandate"), "demand": r.get("demand"),
            } for r in ranked_results])
            _redundant_count = 0
            for _, grp in _rdf.groupby(["alloc", "cap", "obj"]):
                if grp["demand"].nunique() == 1 and grp["rto"].nunique() > 1:
                    _redundant_count += len(grp) - 1
            if _redundant_count > 0:
                st.caption(
                    f"ℹ️ **{_redundant_count} combination(s)** produced identical demand values despite different RTO "
                    "mandates — the mandate was non-binding (base attendance already met or exceeded it). "
                    "These rows show the same demand but may differ in capacity/headroom if cap_red varied."
                )

            # Charts
            valid_ranked = [r for r in ranked_results if not r["opt_status"].startswith("Error")]
            if len(valid_ranked) >= 2:
                tab_bar, tab_heat = st.tabs(["Demand / Capacity Chart", "Metrics Heatmap"])
                with tab_bar:
                    fig_bar = scenario_demand_capacity_bar(valid_ranked)
                    st.plotly_chart(fig_bar, use_container_width=True, key="cmp_bar_chart")
                with tab_heat:
                    fig_heat = scenario_metrics_heatmap(valid_ranked)
                    st.plotly_chart(fig_heat, use_container_width=True, key="cmp_heat_chart")

            # Adopt a scenario
            st.markdown("**Adopt a Scenario**")
            st.caption("Applies the selected scenario's parameters and floor assignments to the active scenario.")
            adoptable = [r for r in ranked_results if not r["opt_status"].startswith("Error")]
            if adoptable and not scenario.is_locked:
                adopt_options = {
                    r["idx"]: (
                        f"#{r['rank']} — "
                        + (f"Alloc {r['alloc_pct']:.0%}, " if r["alloc_pct"] is not None else "")
                        + f"RTO {r['rto_mandate']:.1f}d, Cap Red {r['cap_red']:.0%}, "
                        + {"optimal_placement": "Optimal", "rto_based": "RTO", "rto_whatif": "WI"}.get(r["objective"], r["objective"])
                        + f"  (score {r.get('composite_score', 0):.3f})"
                    )
                    for r in adoptable
                }
                adopt_idx = st.selectbox(
                    "Select scenario to adopt",
                    options=list(adopt_options.keys()),
                    format_func=lambda x: adopt_options[x],
                    key="cmp_adopt_select",
                )
                if st.button("Adopt Selected Scenario", type="primary", key="btn_adopt_matrix"):
                    chosen = next(r for r in adoptable if r["idx"] == adopt_idx)
                    # Apply params
                    rc_adopt = dict(chosen["_rc"])
                    st.session_state["rule_config"] = rc_adopt
                    scenario.params = ScenarioParams(
                        global_rto_mandate_days=(
                            chosen["rto_mandate"] if chosen["objective"] == "optimal_placement" else None
                        ),
                        capacity_reduction_pct=chosen["cap_red"],
                        excluded_floors=scenario.params.excluded_floors,
                    )
                    scenario.floor_assignments = chosen["_assignments"]
                    for alloc in scenario.allocation_results:
                        alloc.allocated_seats = chosen["_unit_allocations"].get(alloc.unit_name, 0)
                        alloc.seat_gap = alloc.allocated_seats - alloc.effective_demand_seats
                    scenario = run_scenario(scenario, units, att_map_raw, raw_floors, rc_adopt)
                    update_scenario(scenario)
                    add_audit_entry(
                        "adopt_matrix_scenario", scenario.scenario_id,
                        "floor_assignments", "rule-based",
                        f"matrix scenario #{chosen['rank']} ({chosen['objective']})",
                        rationale=(
                            f"Adopted from comparison matrix: alloc {chosen['alloc_pct']}, "
                            f"rto {chosen['rto_mandate']}, cap_red {chosen['cap_red']:.0%}, "
                            f"mode {chosen['objective']}"
                        ),
                    )
                    st.success(
                        f"Scenario #{chosen['rank']} adopted — parameters and floor assignments applied. "
                        "Dashboard, Spatial View, and Unit Impact now reflect the changes."
                    )
                    st.session_state.pop("cmp_matrix_results", None)
                    st.rerun()
            elif scenario.is_locked:
                st.warning("Cannot adopt — scenario is locked.")

