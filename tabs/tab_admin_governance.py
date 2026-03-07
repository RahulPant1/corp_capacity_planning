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
    create_baseline_scenario, get_audit_log, get_rule_config,
    set_rule_config, add_audit_entry, is_data_loaded, set_last_data_edit,
    get_units, get_attendance, get_floors, get_active_scenario, update_scenario,
    set_daily_attendance,
)
from config.defaults import PLANNING_BUFFER_PRESETS, DEFAULT_PLANNING_BUFFER


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
            f"Consider buffer planning in the What-If Analysis tab."
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


def _load_full_sample():
    """Load sample data + daily attendance + run policy simulation for a complete demo setup."""
    success = _load_and_validate(generate_buildings_df(), generate_units_df(), generate_attendance_df())
    if not success:
        return

    try:
        from data.sample_data import generate_daily_attendance_df
        from data.loader import parse_daily_attendance
        from engine.scenario_engine import run_scenario
        from engine.forecasting import compute_temporal_clustering

        # Generate and store daily attendance (90 days synthetic data)
        _sample_daily = generate_daily_attendance_df()
        _daily_records = parse_daily_attendance(_sample_daily)
        _daily_df = pd.DataFrame([
            {"date": r.date, "unit_name": r.unit_name, "in_office_count": r.in_office_count}
            for r in _daily_records
        ])
        _daily_df["date"] = pd.to_datetime(_daily_df["date"])
        set_daily_attendance(_daily_records, _daily_df)

        # Run policy simulation so allocation_results + floor_assignments are populated
        _units_list = get_units()
        _att_map = {a.unit_name: a for a in get_attendance()}
        _scen = get_active_scenario()
        _scen = run_scenario(_scen, _units_list, _att_map, get_floors(), get_rule_config())
        update_scenario(_scen)

        # Pre-compute cluster map so What-If cluster toggle is immediately available
        _unit_names = [u.unit_name for u in _units_list]
        _clusters = compute_temporal_clustering(_daily_df, _unit_names)
        if _clusters:
            st.session_state["unit_cluster_map"] = {r["unit_name"]: r["cluster_id"] for r in _clusters}

        # Push sample holiday dates into rule_config for short-term forecast holiday exclusion
        from data.sample_data import get_sample_holiday_dates
        _rc = get_rule_config()
        _rc["holiday_dates"] = get_sample_holiday_dates()
        set_rule_config(_rc)

        st.info(
            "**All tabs pre-loaded for demo:** 90 days of attendance data loaded · "
            "Policy simulation run · Attendance clusters computed · Holiday dates configured. "
            "Demand Analytics, Floor Plan Sandbox, and What-If Analysis are all ready."
        )
    except Exception as e:
        st.warning(f"Base data loaded but demo pre-setup partially failed: {e}")


def render(sidebar_state):
    """Render the Admin & Governance tab."""
    st.header("Admin")

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
        st.caption(
            "Required columns — "
            "**Buildings:** Building ID, Tower ID, Floor Number, Total Seats · "
            "**Units:** Unit Name, Current Total Headcount, HC Growth Forecast (%) · "
            "**Attendance:** Unit Name, Monthly Median In-Office Strength, "
            "Monthly Max In-Office Strength, Avg RTO Days/Week"
        )

        col_upload, col_sample = st.columns(2)
        with col_upload:
            btn_upload_single = st.button("Upload & Validate", type="primary", key="btn_upload_single")
        with col_sample:
            btn_sample_single = st.button("Load Sample Data", key="btn_sample_single")

        if btn_upload_single:
            if single_file:
                try:
                    b_df, u_df, a_df = load_multi_sheet_excel(single_file)
                    _load_and_validate(b_df, u_df, a_df)
                except Exception as e:
                    st.error(f"Error loading file: {e}")
            else:
                st.warning("Please upload an Excel file.")

        if btn_sample_single:
            _load_full_sample()

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
        st.caption(
            "Required columns — "
            "**Buildings:** Building ID, Tower ID, Floor Number, Total Seats · "
            "**Units:** Unit Name, Current Total Headcount, HC Growth Forecast (%) · "
            "**Attendance:** Unit Name, Monthly Median In-Office Strength, "
            "Monthly Max In-Office Strength, Avg RTO Days/Week"
        )

        col_upload, col_sample = st.columns(2)
        with col_upload:
            btn_upload_multi = st.button("Upload & Validate", type="primary", key="btn_upload_multi")
        with col_sample:
            btn_sample_multi = st.button("Load Sample Data", key="btn_sample_multi")

        if btn_upload_multi:
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

        if btn_sample_multi:
            _load_full_sample()

    st.divider()

    # --- Base Data Editor ---
    if is_data_loaded():
        st.subheader("Edit Base Data")
        st.caption("Modify floor capacities, unit headcounts, or attendance data directly. Changes update the baseline immediately.")

        edit_tab1, edit_tab2, edit_tab3 = st.tabs(["Floor Capacities", "Unit Headcount", "Attendance & RTO"])

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
                        set_last_data_edit()
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
                    "Priority": u.business_priority or "None",
                    "Seat Alloc %": (u.seat_alloc_pct * 100) if u.seat_alloc_pct is not None else None,
                    "Night Shift %": u.night_shift_pct * 100,
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
                        new_priority = row["Priority"] if row["Priority"] != "None" else None
                        raw_alloc = row["Seat Alloc %"]
                        new_seat_alloc = float(raw_alloc) / 100.0 if pd.notna(raw_alloc) else None
                        new_night_shift = float(row["Night Shift %"]) / 100.0 if pd.notna(row.get("Night Shift %")) else 0.0

                        if (new_hc != u.current_total_hc or
                            abs(new_growth - u.hc_growth_pct) > 0.001 or
                            new_priority != u.business_priority or
                            new_seat_alloc != u.seat_alloc_pct or
                            abs(new_night_shift - u.night_shift_pct) > 0.001):
                            add_audit_entry(
                                "edit_base_data", "baseline", "unit_data",
                                f"HC={u.current_total_hc},G={u.hc_growth_pct:.1%}",
                                f"HC={new_hc},G={new_growth:.1%},Alloc={new_seat_alloc}",
                                unit_name=u.unit_name,
                                rationale="Manual unit data edit",
                            )
                            u.current_total_hc = new_hc
                            u.hc_growth_pct = new_growth
                            u.business_priority = new_priority
                            u.seat_alloc_pct = new_seat_alloc
                            u.night_shift_pct = new_night_shift
                            changed = True
                    if changed:
                        set_units(current_units)
                        set_last_data_edit()
                        st.success("Unit data updated.")
                        st.rerun()
                    else:
                        st.info("No changes detected.")

        with edit_tab3:
            from data.session_store import get_attendance, set_attendance
            current_attendance = get_attendance()
            if current_attendance:
                att_rows = [{
                    "Unit Name": a.unit_name,
                    "Median In-Office HC": a.monthly_median_hc,
                    "Max In-Office HC": a.monthly_max_hc,
                    "Avg RTO Days/Week": a.avg_rto_days_per_week,
                } for a in current_attendance]
                att_edit_df = pd.DataFrame(att_rows)

                st.caption(
                    "Attendance and RTO behavior data. Used for RTO utilization validation "
                    "and RTO-based optimization objectives."
                )

                edited_att = st.data_editor(
                    att_edit_df,
                    disabled=["Unit Name"],
                    use_container_width=True,
                    key="edit_attendance",
                    num_rows="fixed",
                )

                if st.button("Save Attendance Changes", key="btn_save_attendance"):
                    changed = False
                    for i, a in enumerate(current_attendance):
                        row = edited_att.iloc[i]
                        new_median = float(row["Median In-Office HC"])
                        new_max = float(row["Max In-Office HC"])
                        new_rto = float(row["Avg RTO Days/Week"])

                        if (abs(new_median - a.monthly_median_hc) > 0.01 or
                            abs(new_max - a.monthly_max_hc) > 0.01 or
                            abs(new_rto - a.avg_rto_days_per_week) > 0.01):
                            add_audit_entry(
                                "edit_base_data", "baseline", "attendance",
                                f"Median={a.monthly_median_hc},Max={a.monthly_max_hc},"
                                f"RTO={a.avg_rto_days_per_week}",
                                f"Median={new_median},Max={new_max},"
                                f"RTO={new_rto}",
                                unit_name=a.unit_name,
                                rationale="Manual attendance data edit",
                            )
                            a.monthly_median_hc = new_median
                            a.monthly_max_hc = new_max
                            a.avg_rto_days_per_week = new_rto
                            changed = True
                    if changed:
                        set_attendance(current_attendance)
                        set_last_data_edit()
                        st.success("Attendance data updated.")
                        st.rerun()
                    else:
                        st.info("No changes detected.")

    st.divider()

    # --- Rule Configuration ---
    st.subheader("Rule Configuration")

    config = get_rule_config()

    # Global allocation %
    global_alloc_pct = st.slider(
        "Global Seat Allocation %",
        min_value=0.50, max_value=1.00,
        value=config.get("global_alloc_pct", 0.80),
        step=0.05,
        key="cfg_global_alloc_pct",
        help="Default allocation % applied to all units. "
             "Per-unit overrides (set in Edit Base Data) take precedence.",
    )

    st.caption(
        "Each unit gets the global allocation % of their headcount as seats, "
        "adjusted for growth/attrition over the planning horizon. "
        "Attendance data (Median HC, Max HC, RTO) is used for post-allocation validation."
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

    # Planning Buffer — controls validation sensitivity
    planning_buffer_level = config.get("planning_buffer_level", DEFAULT_PLANNING_BUFFER)

    buffer_labels = {
        "lean": "Lean — tighter validation, plan for typical attendance",
        "balanced": "Balanced — standard buffer for peak days (default)",
        "conservative": "Conservative — extra cushion for worst-case attendance",
    }
    planning_buffer_level = st.radio(
        "Planning Buffer",
        options=list(buffer_labels.keys()),
        format_func=lambda k: buffer_labels[k],
        index=list(buffer_labels.keys()).index(planning_buffer_level)
              if planning_buffer_level in buffer_labels else 1,
        key="cfg_planning_buffer",
        help="Controls how much headroom is expected in post-allocation validation. "
             "Lean = minimal buffer, Conservative = maximum buffer. "
             "Attendance data (Median HC, Max HC, RTO) is always used.",
    )
    st.caption(
        "Planning Buffer controls how peak attendance is weighted in RTO-based validation "
        "(Dashboard alerts, What-If Analysis RTO Status, and RTO-Based optimization). "
        "The **Sensitivity Analysis** in the Optimization tab shows how seat demand varies "
        "across all three presets without changing this global setting."
    )

    # RTO Utilization Alert Threshold
    rto_util_threshold_int = st.slider(
        "RTO Utilization Alert Threshold %",
        min_value=5, max_value=50,
        value=round(config.get("rto_utilization_threshold", 0.20) * 100),
        step=5,
        key="cfg_rto_util_threshold",
        help="Alert when allocated seats exceed RTO-based expected need by this percentage. "
             "Units with allocation above this threshold are flagged as under-utilized.",
    )
    rto_util_threshold = rto_util_threshold_int / 100.0

    if st.button("Save Rule Configuration"):
        # Expand planning buffer preset into individual engine params
        buffer_params = PLANNING_BUFFER_PRESETS.get(planning_buffer_level,
                                                     PLANNING_BUFFER_PRESETS[DEFAULT_PLANNING_BUFFER])
        new_config = {
            "allocation_mode": "simple",
            "global_alloc_pct": global_alloc_pct,
            "min_alloc_pct": min_alloc,
            "max_alloc_pct": max_alloc,
            "planning_buffer_level": planning_buffer_level,
            **buffer_params,
            "rto_utilization_threshold": rto_util_threshold,
        }
        set_rule_config(new_config)
        add_audit_entry("config_change", "global", "rule_config", str(config), str(new_config))
        st.success("Rule configuration saved.")

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

    # --- AI Configuration (hidden) ---
    st.divider()
    with st.expander("🔧 Advanced Settings — AI Configuration", expanded=False):
        st.caption(
            "Enter your Gemini API key to enable the AI Executive Brief feature on the "
            "dashboard. The key is stored for this session only and is never saved to disk."
        )
        key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("gemini_api_key", ""),
            type="password",
            key="admin_gemini_key_input",
            placeholder="AIza...",
        )
        col_save, col_clear = st.columns([1, 1])
        with col_save:
            if st.button("Enable AI Feature", key="btn_save_gemini_key"):
                if key_input.strip():
                    st.session_state["gemini_api_key"] = key_input.strip()
                    st.success(
                        "AI Executive Brief enabled. Switch to Executive Dashboard to use it."
                    )
                else:
                    st.warning("Please enter a valid API key.")
        with col_clear:
            if st.button("Clear Key", key="btn_clear_gemini_key"):
                st.session_state.pop("gemini_api_key", None)
                st.info("API key cleared. AI feature is now disabled.")
