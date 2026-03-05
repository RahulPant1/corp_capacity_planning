"""Tab 4: Scenario Lab — controlled experimentation with planning assumptions."""

import streamlit as st
import pandas as pd
import copy
from datetime import datetime, date

from data.session_store import (
    get_active_scenario, get_scenarios, get_units, get_attendance, get_floors,
    get_rule_config, update_scenario, add_audit_entry, is_data_loaded,
    get_active_scenario_id, get_last_data_edit,
    add_scenario, remove_scenario, set_active_scenario_id,
)
from models.scenario import Scenario, ScenarioOverride, ScenarioParams
from engine.scenario_engine import run_scenario, compare_scenarios, apply_overrides
from engine.allocation_engine import compute_rto_alerts
from engine.report_generator import generate_scenario_report
from components.tables import render_comparison_table
from components.charts import scenario_comparison_bar
from config.defaults import (
    RISK_RED_GAP_PCT, RISK_RED_FRAGMENTATION,
    RISK_AMBER_GAP_PCT, RISK_AMBER_FRAGMENTATION,
    SCENARIO_TYPES,
)


def render(sidebar_state):
    """Render the Scenario Lab tab."""
    st.header("Scenario Lab")

    # ── Manage Scenarios ──────────────────────────────────────────────
    with st.expander("Manage Scenarios", expanded=False):
        mgmt_scenarios = get_scenarios()

        # --- Scenarios list ---
        if mgmt_scenarios:
            scenario_data = []
            for sid, s in mgmt_scenarios.items():
                scenario_data.append({
                    "ID": sid, "Name": s.name, "Type": s.scenario_type,
                    "Horizon": f"{s.planning_horizon_months}mo",
                    "Locked": "🔒 Yes" if s.is_locked else "No",
                    "Overrides": len(s.unit_overrides),
                    "Created": s.created_at.strftime("%Y-%m-%d %H:%M"),
                })
            st.dataframe(pd.DataFrame(scenario_data), use_container_width=True)
            st.caption("**Tip:** Use 'Make Active' to load a scenario below. Locked scenarios (🔒) disable edits.")

            # --- Lock/Unlock | Make Active | Delete ---
            st.caption("**Actions** — select a scenario in each column, then click the button.")
            col1, col2, col3 = st.columns(3)
            with col1:
                non_baseline = [s for s in mgmt_scenarios if s != "baseline"]
                lock_id = st.selectbox("Lock / Unlock", non_baseline or ["(none)"],
                                       key="mgmt_lock_scenario_select")
                if lock_id and lock_id != "(none)" and st.button("Toggle Lock", key="mgmt_btn_toggle_lock"):
                    sc = mgmt_scenarios[lock_id]
                    sc.is_locked = not sc.is_locked
                    update_scenario(sc)
                    add_audit_entry("lock" if sc.is_locked else "unlock", lock_id, "is_locked",
                                    str(not sc.is_locked), str(sc.is_locked))
                    st.rerun()
            with col2:
                make_active_id = st.selectbox("Make Active", list(mgmt_scenarios.keys()),
                                              key="mgmt_make_active_select")
                if st.button("Make Active →", key="mgmt_btn_make_active"):
                    set_active_scenario_id(make_active_id)
                    sc = mgmt_scenarios[make_active_id]
                    lock_note = " (locked 🔒 — edits disabled)" if sc.is_locked else ""
                    st.success(f"Active scenario set to '{sc.name}'{lock_note}.")
                    st.rerun()
            with col3:
                deletable = [s for s in mgmt_scenarios if s != "baseline" and not mgmt_scenarios[s].is_locked]
                del_id = st.selectbox("Delete (permanent)", deletable or ["(none)"], key="mgmt_delete_scenario_select")
                if del_id and del_id != "(none)" and st.button("Delete", type="secondary",
                                                                key="mgmt_btn_delete_scenario"):
                    remove_scenario(del_id)
                    add_audit_entry("delete", del_id, "scenario", del_id, "deleted")
                    st.rerun()

        st.divider()

        # --- Quick-Create from Template ---
        st.caption("**Quick-Create from Template**")
        TEMPLATES = {
            "RTO Mandate (4 days)": {
                "type": "efficiency",
                "desc": "Company-wide 4 days/week in-office mandate. Tests seat demand when attendance rises.",
                "horizon": 6, "params": ScenarioParams(global_rto_mandate_days=4.0), "overrides": None,
            },
            "Aggressive Growth": {
                "type": "growth",
                "desc": "High-priority units grow 25%, others 10%. Tests supply against rapid expansion.",
                "horizon": 6, "params": ScenarioParams(), "overrides": "_growth_heavy",
            },
            "Downsizing (-15% Growth)": {
                "type": "attrition",
                "desc": "All units shrink by 15%. Tests how much seat capacity is freed up.",
                "horizon": 6, "params": ScenarioParams(), "overrides": "_downsizing",
            },
            "Floor Consolidation (Give Up Floors)": {
                "type": "consolidation",
                "desc": "Excludes 4 floors. Simulates subleasing or taking floors offline.",
                "horizon": 6,
                "params": ScenarioParams(excluded_floors=["B1-T1-F4", "B1-T1-F5", "B2-T1-F4", "B2-T1-F5"]),
                "overrides": None,
            },
            "Hybrid Efficiency (Low RTO)": {
                "type": "efficiency",
                "desc": "All units drop to 2 days/week RTO. Tests seat sharing under low attendance.",
                "horizon": 6, "params": ScenarioParams(), "overrides": "_low_rto",
            },
        }
        template_name = st.selectbox("Select template", list(TEMPLATES.keys()), key="mgmt_template_select")
        tmpl = TEMPLATES[template_name]
        st.info(tmpl["desc"])
        if st.button("Create from Template", key="mgmt_btn_create_template"):
            sid = template_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
            sid += "_" + datetime.now().strftime("%H%M%S")
            current_units = get_units() if is_data_loaded() else []
            overrides = {}
            if tmpl["overrides"] == "_growth_heavy":
                for u in current_units:
                    overrides[u.unit_name] = ScenarioOverride(
                        unit_name=u.unit_name,
                        hc_growth_pct=0.25 if u.business_priority == "High" else 0.10)
            elif tmpl["overrides"] == "_downsizing":
                for u in current_units:
                    overrides[u.unit_name] = ScenarioOverride(unit_name=u.unit_name, hc_growth_pct=-0.15)
            elif tmpl["overrides"] == "_low_rto":
                for u in current_units:
                    overrides[u.unit_name] = ScenarioOverride(unit_name=u.unit_name, avg_rto_days=2.0)
            new_s = Scenario(scenario_id=sid, name=template_name, description=tmpl["desc"],
                             scenario_type=tmpl["type"], planning_horizon_months=tmpl["horizon"],
                             params=tmpl["params"], unit_overrides=overrides)
            add_scenario(new_s)
            add_audit_entry("create_template", sid, "scenario", "", template_name)
            st.success(f"'{template_name}' created. Use 'Make Active' above to load it.")
            st.rerun()

        st.divider()

        # --- Create Custom Scenario ---
        st.caption("**Create Custom Scenario**")
        col_a, col_b = st.columns(2)
        with col_a:
            new_name = st.text_input("Scenario Name", key="mgmt_new_scenario_name")
            new_type = st.selectbox("Type", SCENARIO_TYPES, key="mgmt_new_scenario_type")
        with col_b:
            new_horizon = st.selectbox("Planning Horizon (months)", [3, 6], index=1,
                                       key="mgmt_new_scenario_horizon")
            new_desc = st.text_input("Description (optional)", key="mgmt_new_scenario_desc")
        if st.button("Create Scenario", key="mgmt_btn_create_scenario"):
            if not new_name:
                st.warning("Please enter a scenario name.")
            else:
                sid = new_name.lower().replace(" ", "_") + "_" + datetime.now().strftime("%H%M%S")
                new_s = Scenario(scenario_id=sid, name=new_name, description=new_desc,
                                 scenario_type=new_type, planning_horizon_months=new_horizon)
                add_scenario(new_s)
                add_audit_entry("create", sid, "scenario", "", new_name)
                st.success(f"Scenario '{new_name}' created. Use 'Make Active' above to load it.")
                st.rerun()

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin tab.")
        return

    scenarios = get_scenarios()
    scenario = get_active_scenario()

    if not scenario:
        st.info("No active scenario. Use 'Manage Scenarios' above to create one.")
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

    col1, col2 = st.columns(2)
    with col1:
        rto_mandate = st.slider(
            "Global RTO Mandate (days/week)",
            min_value=0.0, max_value=5.0,
            value=scenario.params.global_rto_mandate_days or 0.0,
            step=0.5,
            key="scenario_rto_mandate",
            disabled=scenario.is_locked,
            help="Set a minimum RTO target. Units below this are flagged as non-compliant.",
        )
    with col2:
        floors = get_floors()
        all_floor_ids = sorted(set(f.floor_id for f in floors))
        valid_excluded = [f for f in scenario.params.excluded_floors if f in all_floor_ids]
        excluded = st.multiselect(
            "Excluded Floors",
            all_floor_ids,
            default=valid_excluded,
            key="scenario_excluded_floors",
            disabled=scenario.is_locked,
            help="Remove specific floors from the available supply (e.g., renovation, sublease).",
        )

    st.divider()

    # --- Unit-Level Override Table ---
    st.subheader("Unit-Level Overrides")

    rule_config = get_rule_config()
    alloc_mode = rule_config.get("allocation_mode", "simple")

    units = get_units()
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}

    st.caption(
        "Adjust Growth % per unit (positive = expansion, negative = downsizing). "
        "Use **Alloc % Override** to pin a specific allocation % for a unit."
    )

    # Build editable dataframe — scenario values only (pre-filled from baseline)
    rows = []
    for u in units:
        att = att_map.get(u.unit_name)
        override = scenario.unit_overrides.get(u.unit_name, ScenarioOverride(unit_name=u.unit_name))

        row = {
            "Unit": u.unit_name,
            "Growth %": (override.hc_growth_pct if override.hc_growth_pct is not None else u.hc_growth_pct) * 100,
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

        allocs = scenario.allocation_results

        # Summary metric cards
        _total_demand = sum(a.effective_demand_seats for a in allocs)
        _total_alloc = sum(a.allocated_seats for a in allocs)
        _net_gap = _total_alloc - _total_demand
        _at_risk = sum(
            1 for a in allocs
            if (a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0)
            < RISK_AMBER_GAP_PCT
        )
        _total_hot_seat_savings = sum(a.hot_seat_savings for a in allocs)
        if _total_hot_seat_savings > 0:
            m1, m2, m3, m4, m5 = st.columns(5)
        else:
            m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Demand", f"{_total_demand:,}")
        m2.metric("Total Allocated", f"{_total_alloc:,}")
        m3.metric("Net Gap", f"{_net_gap:+,}",
                  delta_color="normal" if _net_gap >= 0 else "inverse")
        m4.metric("Units at Risk", str(_at_risk),
                  delta_color="inverse" if _at_risk > 0 else "normal")
        if _total_hot_seat_savings > 0:
            m5.metric("Hot-Seat Savings", f"{_total_hot_seat_savings:,}",
                      help="Seats saved via night-shift hot-seating (day/night desk sharing)")

        # Compute RTO data for table enrichment
        att_profiles = get_attendance()
        att_map_rto = {a.unit_name: a for a in att_profiles}
        _, scenario_att_map = apply_overrides(units, att_map_rto, scenario)
        rto_alerts_data = compute_rto_alerts(allocs, units, scenario_att_map, get_rule_config())
        rto_alert_map = {ra["unit_name"]: ra for ra in rto_alerts_data}

        # RTO compliance lookup
        has_rto_mandate = (
            scenario.params.global_rto_mandate_days
            and scenario.params.global_rto_mandate_days > 0
        )
        rto_compliance_map = {}
        if has_rto_mandate:
            from engine.allocation_engine import compute_rto_compliance
            compliance = compute_rto_compliance(att_map_rto, scenario.params.global_rto_mandate_days)
            rto_compliance_map = {rc["unit_name"]: rc for rc in compliance}

        # Build enriched table
        unit_map_results = {u.unit_name: u for u in units}
        opt_applied = any(a.allocated_seats != a.effective_demand_seats for a in allocs)
        result_rows = []
        for a in allocs:
            ra = rto_alert_map.get(a.unit_name)
            rc = rto_compliance_map.get(a.unit_name)

            rto_need = ra["expected_seats"] if ra else "—"

            if has_rto_mandate and rc:
                if rc["compliant"]:
                    rto_status = f"{rc['actual_rto']:.1f} / {rc['target_rto']:.1f} ✓"
                else:
                    rto_status = f"{rc['actual_rto']:.1f} / {rc['target_rto']:.1f} ✗"
            else:
                rto_status = "N/A"

            u_res = unit_map_results.get(a.unit_name)
            proj_hc = round(u_res.projected_hc(scenario.planning_horizon_months)) if u_res else 0
            effective_alloc_pct = a.allocated_seats / proj_hc if proj_hc > 0 else 0.0

            result_rows.append({
                "Unit": a.unit_name,
                "Policy Alloc %": f"{a.recommended_alloc_pct:.1%}",
                "Effective Alloc %": f"{effective_alloc_pct:.1%}",
                "Policy Demand": a.effective_demand_seats,
                "Allocated Seats": a.allocated_seats,
                "Gap (vs Policy)": a.seat_gap,
                "RTO Need": rto_need,
                "RTO Status": rto_status,
                "Fragmentation": f"{a.fragmentation_score:.2f}",
                "Overridden": "Yes" if a.is_overridden else "",
            })

        if opt_applied:
            st.info(
                "Optimization applied — **Allocated Seats** and **Gap (vs Policy)** reflect "
                "optimizer output. **Policy Alloc %** and **Policy Demand** remain rule-based "
                "for comparison."
            )
        st.dataframe(pd.DataFrame(result_rows), use_container_width=True)
        st.caption(
            "**Policy Alloc %** = desk-ratio rule from Admin settings. "
            "**Effective Alloc %** = Allocated Seats ÷ Projected HC. "
            "**Gap (vs Policy)** = Allocated − Policy Demand (negative = shortfall). "
            "**Fragmentation (0–1):** 0 = all on one floor (ideal). "
            "**RTO Status** (if RTO mandate set): actual / target days/week with ✓/✗."
        )

        # Allocation % formula expander
        with st.expander("How is Allocation % calculated?", expanded=False):
            config_for_exp = get_rule_config()
            global_pct = config_for_exp.get("global_alloc_pct", 0.80)
            min_pct = config_for_exp.get("min_alloc_pct", 0.20)
            max_pct = config_for_exp.get("max_alloc_pct", 1.50)
            horizon = scenario.planning_horizon_months
            st.markdown(
                f"**Formula (Simple mode):**\n\n"
                f"```\nAlloc % = Global% × (1 + Growth% × Months/12)\n"
                f"        = {global_pct:.0%} × (1 + Growth% × {horizon}/12)\n"
                f"then clamped to [{min_pct:.0%} – {max_pct:.0%}] policy bounds\n"
                f"Effective Demand = Alloc% × Current HC\n```"
            )
            non_overridden = [a for a in allocs if not a.is_overridden and a.explanation_steps]
            if non_overridden:
                st.markdown("**Example — " + non_overridden[0].unit_name + ":**")
                for step in non_overridden[0].explanation_steps:
                    st.markdown(f"- {step}")
            overridden = [a for a in allocs if a.is_overridden]
            if overridden:
                st.markdown(
                    f"**{len(overridden)} unit(s) have a manual Alloc % Override** — "
                    "their allocation % was set directly rather than computed by the formula."
                )

        # --- Scenario Impact Summary (English narrative) ---
        st.divider()
        st.subheader("Scenario Impact Summary")

        total_demand = sum(a.effective_demand_seats for a in allocs)
        total_allocated = sum(a.allocated_seats for a in allocs)
        total_gap = total_allocated - total_demand
        num_units = len(allocs)

        st.markdown(
            f"This scenario allocates **{total_allocated:,} seats** across "
            f"**{num_units} units**. Total demand is **{total_demand:,} seats**, "
            f"leaving a net gap of **{total_gap:+,} seats**."
        )

        # RTO Need explanation
        total_rto_need = sum(
            rto_alert_map[a.unit_name]["expected_seats"]
            for a in allocs if a.unit_name in rto_alert_map
        )
        st.markdown(
            f"**RTO Need** reflects how many seats each unit actually requires based on "
            f"real attendance patterns: *(Median HC + Peak Buffer) x (RTO Days / 5)*. "
            f"Total RTO-based need across all units is **{total_rto_need:,} seats** "
            f"vs **{total_allocated:,} allocated**."
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

        # --- Download Report ---
        st.divider()
        with st.expander("Download Report", expanded=False):
            st.caption(
                "Export an Excel report of this scenario for management review. "
                "Includes allocation results, floor assignments, risks, and the most recent optimization run (if any)."
            )
            opt_history = st.session_state.get("optimization_history", [])
            report_bytes = generate_scenario_report(
                scenario=scenario,
                floors=floors,
                units=units,
                attendance_map={a.unit_name: a for a in attendance_profiles},
                rule_config=get_rule_config(),
                opt_history=opt_history if opt_history else None,
            )
            file_name = f"scenario_{scenario.name.replace(' ', '_')}_{date.today()}.xlsx"
            st.download_button(
                label="Download Scenario Report (.xlsx)",
                data=report_bytes,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_download_report",
            )

            # PDF boardroom report
            from engine.pdf_report_generator import generate_pdf_report
            pdf_bytes = generate_pdf_report(
                scenario=scenario,
                floors=floors,
                units=units,
                attendance_map={a.unit_name: a for a in attendance_profiles},
                rule_config=get_rule_config(),
                opt_history=opt_history if opt_history else None,
            )
            pdf_name = f"scenario_{scenario.name.replace(' ', '_')}_{date.today()}.pdf"
            st.download_button(
                label="Download Boardroom Report (.pdf)",
                data=pdf_bytes,
                file_name=pdf_name,
                mime="application/pdf",
                key="btn_download_pdf",
            )

        # --- Sensitivity Analysis (AI) ---
        st.divider()
        with st.expander("Sensitivity Analysis", expanded=False):
            st.caption(
                "Automatically varies key planning parameters one at a time and measures "
                "the impact on total seat gap. Identifies which levers matter most."
            )

            if st.button("Run Sensitivity Analysis", key="btn_sensitivity"):
                from engine.sensitivity import (
                    run_sensitivity_analysis, get_parameter_impact_summary,
                )
                from components.charts import tornado_chart

                with st.spinner("Running sensitivity analysis (this may take a moment)..."):
                    att_map_sens = {a.unit_name: a for a in attendance_profiles}
                    sens_results = run_sensitivity_analysis(
                        scenario, units, att_map_sens, floors, get_rule_config(),
                    )

                if sens_results:
                    fig = tornado_chart(sens_results)
                    st.plotly_chart(fig, use_container_width=True)

                    param_summary = get_parameter_impact_summary(sens_results)
                    st.markdown("**Parameter Impact Ranking:**")
                    summary_rows = []
                    for ps in param_summary:
                        summary_rows.append({
                            "Parameter": ps["parameter"],
                            "Impact Range (seats)": f"{ps['range']:+,}",
                            "Max Positive": f"{ps['max_positive_delta']:+,}",
                            "Max Negative": f"{ps['max_negative_delta']:+,}",
                            "Most Impactful Variation": ps["most_impactful_variation"],
                        })
                    st.dataframe(pd.DataFrame(summary_rows),
                                 use_container_width=True, hide_index=True)

                    with st.expander("Detailed Results", expanded=False):
                        detail_rows = []
                        for r in sens_results:
                            detail_rows.append({
                                "Parameter": r["parameter"],
                                "Variation": r["variation_label"],
                                "New Value": r["variation_value"],
                                "Baseline Gap": r["baseline_gap"],
                                "Result Gap": r["result_gap"],
                                "Delta": f"{r['gap_delta']:+,}",
                            })
                        st.dataframe(pd.DataFrame(detail_rows),
                                     use_container_width=True, hide_index=True)
                else:
                    st.info("No sensitivity results generated.")
