"""Tab 6: Admin & Governance — data upload, rule config, scenario management, audit trail."""

import streamlit as st
import pandas as pd
import os
from datetime import datetime

from data.loader import load_file, load_multi_sheet_excel, parse_buildings, parse_units, parse_attendance
from data.validator import (
    validate_buildings, validate_units, validate_attendance, validate_cross_file,
)
from data.sample_data import generate_buildings_df, generate_units_df, generate_attendance_df
from data.session_store import (
    set_floors, set_units, set_attendance, set_data_loaded,
    get_scenarios, get_active_scenario_id, add_scenario, remove_scenario,
    update_scenario, create_baseline_scenario, get_audit_log, get_rule_config,
    set_rule_config, add_audit_entry, is_data_loaded,
)
from models.scenario import Scenario, ScenarioParams
from config.defaults import SCENARIO_TYPES


def _load_and_validate(buildings_df, units_df, attendance_df):
    """Validate and store uploaded data."""
    errors = []
    warnings = []

    # Validate each file
    b_result = validate_buildings(buildings_df)
    u_result = validate_units(units_df)
    a_result = validate_attendance(attendance_df)

    for r in [b_result, u_result, a_result]:
        errors.extend(r.errors)
        warnings.extend(r.warnings)

    if not errors:
        cross = validate_cross_file(units_df, attendance_df)
        warnings.extend(cross.warnings)

    if errors:
        for e in errors:
            st.error(e)
        return False

    for w in warnings:
        st.warning(w)

    # Parse and store
    floors = parse_buildings(buildings_df)
    units = parse_units(units_df)
    attendance = parse_attendance(attendance_df)

    set_floors(floors)
    set_units(units)
    set_attendance(attendance)
    set_data_loaded(True)

    # Create baseline scenario
    horizon = st.session_state.get("sidebar_state", {}).get("planning_horizon", 6)
    create_baseline_scenario(horizon)

    add_audit_entry("upload", "baseline", "all_data", "", "uploaded", rationale="Data upload")

    st.success(f"Data loaded: {len(floors)} floors, {len(units)} units, {len(attendance)} attendance profiles")

    # --- Immediate supply vs demand health check ---
    total_seats = sum(f.total_seats for f in floors)
    total_hc = sum(u.current_total_hc for u in units)
    att_map = {a.unit_name: a for a in attendance}
    total_median = sum(att_map[u.unit_name].monthly_median_hc
                       for u in units if u.unit_name in att_map)
    total_peak = sum(att_map[u.unit_name].monthly_max_hc
                     for u in units if u.unit_name in att_map)

    st.divider()
    st.subheader("Data Health Check")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Seats", f"{total_seats:,}")
    col2.metric("Total Headcount", f"{total_hc:,}")
    col3.metric("Median In-Office", f"{total_median:,}")
    col4.metric("Peak In-Office", f"{total_peak:,}")

    if total_hc > total_seats:
        st.error(
            f"RISK: Total headcount ({total_hc:,}) exceeds total seat supply ({total_seats:,}). "
            f"There is a deficit of {total_hc - total_seats:,} seats even before applying allocation logic. "
            f"Scarcity redistribution will be required."
        )
    elif total_peak > total_seats:
        st.warning(
            f"WARNING: Peak in-office strength ({total_peak:,}) exceeds total seats ({total_seats:,}). "
            f"On peak days, {total_peak - total_seats:,} employees may not have seats. "
            f"Consider buffer planning in the Scenario Lab."
        )
    elif total_median > total_seats * 0.85:
        st.warning(
            f"CAUTION: Median in-office strength ({total_median:,}) is at "
            f"{total_median/total_seats:.0%} of total seats ({total_seats:,}). "
            f"Limited headroom for growth or peak days."
        )
    else:
        st.success(
            f"Supply looks healthy. Median utilization at {total_median/total_seats:.0%}, "
            f"peak at {total_peak/total_seats:.0%} of {total_seats:,} seats."
        )

    return True


def render(sidebar_state):
    """Render the Admin & Governance tab."""
    st.header("Admin & Governance")

    # --- Data Upload Section ---
    st.subheader("Data Upload")

    upload_mode = st.radio(
        "Upload mode",
        ["Single Excel file (3 tabs)", "Three separate files"],
        horizontal=True,
        key="upload_mode",
    )

    if upload_mode == "Single Excel file (3 tabs)":
        st.caption(
            "Upload one `.xlsx` file with three sheets named: "
            "**Buildings**, **Units**, **Attendance** "
            "(also accepts aliases like 'Building Master', 'Headcount', 'RTO', etc.)"
        )
        single_file = st.file_uploader(
            "Excel workbook with 3 tabs",
            type=["xlsx"],
            key="upload_single",
        )

        col_upload, col_sample = st.columns(2)
        with col_upload:
            if st.button("Upload & Validate", type="primary", key="btn_upload_single"):
                if single_file:
                    try:
                        b_df, u_df, a_df = load_multi_sheet_excel(single_file)
                        _load_and_validate(b_df, u_df, a_df)
                    except Exception as e:
                        st.error(f"Error loading file: {e}")
                else:
                    st.warning("Please upload an Excel file.")

        with col_sample:
            if st.button("Load Sample Data", key="btn_sample_single"):
                b_df = generate_buildings_df()
                u_df = generate_units_df()
                a_df = generate_attendance_df()
                _load_and_validate(b_df, u_df, a_df)

    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            buildings_file = st.file_uploader(
                "Building & Floor Master",
                type=["csv", "xlsx"],
                key="upload_buildings",
            )
        with col2:
            units_file = st.file_uploader(
                "Unit Headcount & Forecast",
                type=["csv", "xlsx"],
                key="upload_units",
            )
        with col3:
            attendance_file = st.file_uploader(
                "Attendance & RTO Behavior",
                type=["csv", "xlsx"],
                key="upload_attendance",
            )

        col_upload, col_sample = st.columns(2)
        with col_upload:
            if st.button("Upload & Validate", type="primary", key="btn_upload_multi"):
                if buildings_file and units_file and attendance_file:
                    try:
                        b_df = load_file(buildings_file)
                        u_df = load_file(units_file)
                        a_df = load_file(attendance_file)
                        _load_and_validate(b_df, u_df, a_df)
                    except Exception as e:
                        st.error(f"Error loading files: {e}")
                else:
                    st.warning("Please upload all three files.")

        with col_sample:
            if st.button("Load Sample Data", key="btn_sample_multi"):
                b_df = generate_buildings_df()
                u_df = generate_units_df()
                a_df = generate_attendance_df()
                _load_and_validate(b_df, u_df, a_df)

    st.divider()

    # --- Base Data Editor ---
    if is_data_loaded():
        st.subheader("Edit Base Data")
        st.caption("Modify floor capacities or unit headcounts directly. Changes update the baseline immediately.")

        edit_tab1, edit_tab2 = st.tabs(["Floor Capacities", "Unit Headcount"])

        with edit_tab1:
            from data.session_store import get_floors, set_floors
            current_floors = get_floors()
            if current_floors:
                floor_rows = [{
                    "Floor ID": f.floor_id,
                    "Building": f.building_name,
                    "Tower": f.tower_id,
                    "Floor #": f.floor_number,
                    "Total Seats": f.total_seats,
                } for f in current_floors]
                floor_edit_df = pd.DataFrame(floor_rows)

                edited_floors = st.data_editor(
                    floor_edit_df,
                    disabled=["Floor ID", "Building", "Tower", "Floor #"],
                    use_container_width=True,
                    key="edit_floor_capacity",
                    num_rows="fixed",
                )

                if st.button("Save Floor Changes", key="btn_save_floors"):
                    changed = False
                    for i, f in enumerate(current_floors):
                        new_seats = int(edited_floors.iloc[i]["Total Seats"])
                        if new_seats != f.total_seats:
                            add_audit_entry(
                                "edit_base_data", "baseline", "total_seats",
                                str(f.total_seats), str(new_seats),
                                unit_name=f.floor_id,
                                rationale="Manual floor capacity edit",
                            )
                            f.total_seats = new_seats
                            changed = True
                    if changed:
                        set_floors(current_floors)
                        st.success("Floor capacities updated.")
                        st.rerun()
                    else:
                        st.info("No changes detected.")

        with edit_tab2:
            from data.session_store import get_units, set_units
            current_units = get_units()
            if current_units:
                unit_rows = [{
                    "Unit Name": u.unit_name,
                    "Current Total HC": u.current_total_hc,
                    "Growth %": u.hc_growth_pct * 100,
                    "Attrition %": u.attrition_pct * 100,
                    "Priority": u.business_priority or "None",
                    "Seat Alloc %": (u.seat_alloc_pct * 100) if u.seat_alloc_pct is not None else None,
                } for u in current_units]
                unit_edit_df = pd.DataFrame(unit_rows)

                st.caption(
                    "**Seat Alloc %**: Per-unit allocation override (Simple mode). "
                    "Leave blank to use the global default."
                )

                edited_units = st.data_editor(
                    unit_edit_df,
                    disabled=["Unit Name"],
                    use_container_width=True,
                    key="edit_unit_hc",
                    num_rows="fixed",
                )

                if st.button("Save Unit Changes", key="btn_save_units"):
                    changed = False
                    for i, u in enumerate(current_units):
                        row = edited_units.iloc[i]
                        new_hc = int(row["Current Total HC"])
                        new_growth = float(row["Growth %"]) / 100.0
                        new_attrition = float(row["Attrition %"]) / 100.0
                        new_priority = row["Priority"] if row["Priority"] != "None" else None
                        raw_alloc = row["Seat Alloc %"]
                        new_seat_alloc = float(raw_alloc) / 100.0 if pd.notna(raw_alloc) else None

                        if (new_hc != u.current_total_hc or
                            abs(new_growth - u.hc_growth_pct) > 0.001 or
                            abs(new_attrition - u.attrition_pct) > 0.001 or
                            new_priority != u.business_priority or
                            new_seat_alloc != u.seat_alloc_pct):
                            add_audit_entry(
                                "edit_base_data", "baseline", "unit_data",
                                f"HC={u.current_total_hc},G={u.hc_growth_pct:.1%},A={u.attrition_pct:.1%}",
                                f"HC={new_hc},G={new_growth:.1%},A={new_attrition:.1%},Alloc={new_seat_alloc}",
                                unit_name=u.unit_name,
                                rationale="Manual unit data edit",
                            )
                            u.current_total_hc = new_hc
                            u.hc_growth_pct = new_growth
                            u.attrition_pct = new_attrition
                            u.business_priority = new_priority
                            u.seat_alloc_pct = new_seat_alloc
                            changed = True
                    if changed:
                        set_units(current_units)
                        st.success("Unit data updated.")
                        st.rerun()
                    else:
                        st.info("No changes detected.")

    st.divider()

    # --- Rule Configuration ---
    st.subheader("Rule Configuration")

    config = get_rule_config()

    # Allocation mode toggle
    alloc_mode_options = ["Simple", "Advanced"]
    current_mode = config.get("allocation_mode", "simple")
    alloc_mode = st.radio(
        "Allocation Mode",
        alloc_mode_options,
        index=0 if current_mode == "simple" else 1,
        horizontal=True,
        key="cfg_alloc_mode",
        help="**Simple**: Uses a flat allocation % (global or per-unit). "
             "**Advanced**: Derives allocation from attendance data (median, peak, RTO, stability).",
    )
    alloc_mode_value = "simple" if alloc_mode == "Simple" else "advanced"

    # Global allocation % — always visible
    global_alloc_pct = st.slider(
        "Global Seat Allocation %",
        min_value=0.50, max_value=1.00,
        value=config.get("global_alloc_pct", 0.80),
        step=0.05,
        key="cfg_global_alloc_pct",
        help="Default allocation % applied to all units in Simple mode. "
             "Per-unit overrides (set in Edit Base Data) take precedence.",
    )

    if alloc_mode_value == "simple":
        st.caption(
            "Simple mode: Each unit gets the global allocation % of their headcount as seats, "
            "adjusted for growth/attrition over the planning horizon. "
            "Set per-unit overrides in Edit Base Data > Unit Headcount > Seat Alloc % column."
        )

    with st.expander("Allocation Policy Bounds", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            min_alloc = st.slider(
                "Minimum Allocation %", 0.0, 1.0, config.get("min_alloc_pct", 0.20),
                step=0.05, key="cfg_min_alloc",
            )
        with col2:
            max_alloc = st.slider(
                "Maximum Allocation %", 0.5, 2.0, config.get("max_alloc_pct", 1.50),
                step=0.05, key="cfg_max_alloc",
            )

    # Buffer & Scaling — only shown in Advanced mode
    stability_threshold = config.get("stability_discount_threshold", 0.7)
    stability_discount = config.get("stability_discount_factor", 0.30)
    buffer_mult = config.get("peak_buffer_multiplier", 1.0)
    shrink_factor = config.get("shrink_contribution_factor", 0.5)

    if alloc_mode_value == "advanced":
        with st.expander("Buffer & Scaling Parameters (Advanced)", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                stability_threshold = st.slider(
                    "Stability Discount Threshold", 0.0, 1.0,
                    config.get("stability_discount_threshold", 0.7),
                    step=0.05, key="cfg_stability_threshold",
                )
                stability_discount = st.slider(
                    "Stability Discount Factor", 0.0, 1.0,
                    config.get("stability_discount_factor", 0.30),
                    step=0.05, key="cfg_stability_discount",
                )
            with col2:
                buffer_mult = st.slider(
                    "Peak Buffer Multiplier", 0.5, 2.0,
                    config.get("peak_buffer_multiplier", 1.0),
                    step=0.1, key="cfg_buffer_mult",
                )
                shrink_factor = st.slider(
                    "Shrink Contribution Factor", 0.0, 1.0,
                    config.get("shrink_contribution_factor", 0.5),
                    step=0.1, key="cfg_shrink_factor",
                )

    if st.button("Save Rule Configuration"):
        new_config = {
            "allocation_mode": alloc_mode_value,
            "global_alloc_pct": global_alloc_pct,
            "min_alloc_pct": min_alloc,
            "max_alloc_pct": max_alloc,
            "stability_discount_threshold": stability_threshold,
            "stability_discount_factor": stability_discount,
            "peak_buffer_multiplier": buffer_mult,
            "shrink_contribution_factor": shrink_factor,
        }
        set_rule_config(new_config)
        add_audit_entry("config_change", "global", "rule_config", str(config), str(new_config))
        st.success("Rule configuration saved.")

    st.divider()

    # --- Scenario Management ---
    st.subheader("Scenario Management")

    scenarios = get_scenarios()
    if scenarios:
        scenario_data = []
        for sid, s in scenarios.items():
            scenario_data.append({
                "ID": sid,
                "Name": s.name,
                "Type": s.scenario_type,
                "Horizon": f"{s.planning_horizon_months}mo",
                "Locked": "Yes" if s.is_locked else "No",
                "Overrides": len(s.unit_overrides),
                "Created": s.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        st.dataframe(pd.DataFrame(scenario_data), use_container_width=True)

        # Lock/Unlock
        col1, col2 = st.columns(2)
        with col1:
            lock_id = st.selectbox("Select scenario to lock/unlock",
                                    [s for s in scenarios if s != "baseline"],
                                    key="lock_scenario_select")
            if lock_id and st.button("Toggle Lock"):
                s = scenarios[lock_id]
                s.is_locked = not s.is_locked
                update_scenario(s)
                action = "lock" if s.is_locked else "unlock"
                add_audit_entry(action, lock_id, "is_locked", str(not s.is_locked), str(s.is_locked))
                st.rerun()

        with col2:
            del_id = st.selectbox("Select scenario to delete",
                                   [s for s in scenarios if s != "baseline" and not scenarios[s].is_locked],
                                   key="delete_scenario_select")
            if del_id and st.button("Delete Scenario", type="secondary"):
                remove_scenario(del_id)
                add_audit_entry("delete", del_id, "scenario", del_id, "deleted")
                st.rerun()

    # Quick-create scenario templates
    from models.scenario import ScenarioOverride
    with st.expander("Quick-Create from Template", expanded=False):
        st.caption("Pre-built scenarios with sensible defaults. Select one and click Create.")

        TEMPLATES = {
            "RTO Mandate (4 days)": {
                "type": "efficiency",
                "desc": "Simulates a company-wide mandate requiring 4 days/week in-office. "
                        "Tests impact on seat demand when attendance increases.",
                "horizon": 6,
                "params": ScenarioParams(global_rto_mandate_days=4.0),
                "overrides": {},
            },
            "Aggressive Growth": {
                "type": "growth",
                "desc": "All high-priority units grow by 25%, others by 10%. "
                        "Tests whether current seat supply can handle rapid expansion.",
                "horizon": 6,
                "params": ScenarioParams(),
                "overrides": "_growth_heavy",
            },
            "High Attrition / Downsizing": {
                "type": "attrition",
                "desc": "All units experience 15% attrition with 0% growth. "
                        "Tests how much seat capacity is freed up for reallocation.",
                "horizon": 6,
                "params": ScenarioParams(),
                "overrides": "_attrition_heavy",
            },
            "Floor Consolidation (-20% capacity)": {
                "type": "consolidation",
                "desc": "Reduces seat capacity by 20% across all floors. "
                        "Simulates giving up floors or renovations that reduce usable seats.",
                "horizon": 6,
                "params": ScenarioParams(capacity_reduction_pct=0.20),
                "overrides": {},
            },
            "Hybrid Efficiency (Low RTO)": {
                "type": "efficiency",
                "desc": "All units drop to 2 days/week RTO. "
                        "Tests how much seat sharing improves when attendance is low.",
                "horizon": 6,
                "params": ScenarioParams(),
                "overrides": "_low_rto",
            },
        }

        template_name = st.selectbox(
            "Select template",
            list(TEMPLATES.keys()),
            key="template_select",
        )
        tmpl = TEMPLATES[template_name]
        st.info(tmpl["desc"])

        if st.button("Create from Template", key="btn_create_template"):
            sid = template_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
            sid += "_" + datetime.now().strftime("%H%M%S")

            # Build overrides based on template type
            overrides = {}
            current_units = get_units() if is_data_loaded() else []

            if tmpl["overrides"] == "_growth_heavy":
                for u in current_units:
                    growth = 0.25 if u.business_priority == "High" else 0.10
                    overrides[u.unit_name] = ScenarioOverride(
                        unit_name=u.unit_name, hc_growth_pct=growth, attrition_pct=0.03,
                    )
            elif tmpl["overrides"] == "_attrition_heavy":
                for u in current_units:
                    overrides[u.unit_name] = ScenarioOverride(
                        unit_name=u.unit_name, hc_growth_pct=0.0, attrition_pct=0.15,
                    )
            elif tmpl["overrides"] == "_low_rto":
                for u in current_units:
                    overrides[u.unit_name] = ScenarioOverride(
                        unit_name=u.unit_name, avg_rto_days=2.0,
                    )

            scenario = Scenario(
                scenario_id=sid,
                name=template_name,
                description=tmpl["desc"],
                scenario_type=tmpl["type"],
                planning_horizon_months=tmpl["horizon"],
                params=tmpl["params"],
                unit_overrides=overrides,
            )
            add_scenario(scenario)
            add_audit_entry("create_template", sid, "scenario", "", template_name)
            st.success(f"Scenario '{template_name}' created. Switch to it in the sidebar, then Run Simulation in the Scenario Lab.")
            st.rerun()

    # Create custom scenario
    with st.expander("Create Custom Scenario", expanded=False):
        new_name = st.text_input("Scenario Name", key="new_scenario_name")
        new_type = st.selectbox("Scenario Type", SCENARIO_TYPES, key="new_scenario_type")
        new_desc = st.text_area("Description", key="new_scenario_desc")
        new_horizon = st.selectbox("Planning Horizon", [3, 6], index=1, key="new_scenario_horizon")

        if st.button("Create Scenario"):
            if not new_name:
                st.warning("Please enter a scenario name.")
            else:
                sid = new_name.lower().replace(" ", "_") + "_" + datetime.now().strftime("%H%M%S")
                scenario = Scenario(
                    scenario_id=sid,
                    name=new_name,
                    description=new_desc,
                    scenario_type=new_type,
                    planning_horizon_months=new_horizon,
                )
                add_scenario(scenario)
                add_audit_entry("create", sid, "scenario", "", new_name)
                st.success(f"Scenario '{new_name}' created.")
                st.rerun()

    st.divider()

    # --- Audit Trail ---
    st.subheader("Audit Trail")

    audit_log = get_audit_log()
    if audit_log:
        audit_data = []
        for entry in reversed(audit_log):
            audit_data.append({
                "Timestamp": entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Action": entry.action,
                "Scenario": entry.scenario_id,
                "Unit": entry.unit_name or "—",
                "Field": entry.field_changed,
                "Old Value": entry.old_value[:50],
                "New Value": entry.new_value[:50],
                "Rationale": entry.rationale,
            })
        audit_df = pd.DataFrame(audit_data)
        st.dataframe(audit_df, use_container_width=True, height=300)

        csv = audit_df.to_csv(index=False)
        st.download_button("Export Audit Log (CSV)", csv, "audit_log.csv", "text/csv")
    else:
        st.info("No audit entries yet.")
