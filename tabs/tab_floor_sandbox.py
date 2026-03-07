"""Tab 7: Floor Plan Sandbox — import an existing layout, edit it, and simulate impact."""

import copy as _copy
import streamlit as st
import pandas as pd
from typing import List

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_attendance, get_rule_config,
    update_scenario, add_audit_entry, is_data_loaded, get_cluster_map,
)
from engine.scenario_engine import run_scenario, apply_floor_modifications, apply_overrides
from models.allocation import FloorAssignment
from config.defaults import RISK_RED_GAP_PCT, RISK_AMBER_GAP_PCT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _floor_lookup(raw_floors):
    """Build lookup: (tower_id, floor_number) -> Floor."""
    return {(f.tower_id, f.floor_number): f for f in raw_floors}


def _parse_plan_upload(df: pd.DataFrame, raw_floors) -> List[FloorAssignment]:
    """Parse a DataFrame into FloorAssignment list. Raises ValueError on bad data."""
    df.columns = [c.strip() for c in df.columns]
    # Find required columns case-insensitively
    required = {"unit": None, "tower": None, "floor": None, "seats assigned": None}
    for key in list(required.keys()):
        for col in df.columns:
            if col.strip().lower() == key:
                required[key] = col
                break
        if required[key] is None:
            raise ValueError(
                f"Missing required column: '{key}'. "
                "Expected columns: Unit, Tower, Floor, Seats Assigned"
            )

    lookup = _floor_lookup(raw_floors)
    assignments = []
    errors = []
    for i, row in df.iterrows():
        unit = str(row[required["unit"]]).strip()
        tower = str(row[required["tower"]]).strip()
        try:
            floor_num = int(row[required["floor"]])
        except (ValueError, TypeError):
            errors.append(f"Row {i + 2}: Floor must be an integer, got '{row[required['floor']]}'")
            continue
        try:
            seats = int(row[required["seats assigned"]])
        except (ValueError, TypeError):
            errors.append(
                f"Row {i + 2}: Seats Assigned must be an integer, "
                f"got '{row[required['seats assigned']]}'"
            )
            continue

        floor_obj = lookup.get((tower, floor_num))
        if floor_obj is None:
            errors.append(f"Row {i + 2}: Tower '{tower}' Floor {floor_num} not found in floor master")
            continue
        if seats < 0:
            errors.append(f"Row {i + 2}: Seats Assigned cannot be negative")
            continue

        assignments.append(FloorAssignment(
            unit_name=unit,
            building_id=floor_obj.building_id,
            tower_id=tower,
            floor_number=floor_num,
            seats_assigned=seats,
            adjacency_tier="custom",
        ))

    if errors:
        raise ValueError("Parse errors:\n" + "\n".join(errors))
    return assignments


def _assignments_to_df(assignments: List[FloorAssignment], raw_floors) -> pd.DataFrame:
    """Convert FloorAssignment list to display DataFrame."""
    lookup = _floor_lookup(raw_floors)
    rows = []
    for fa in assignments:
        floor_obj = lookup.get((fa.tower_id, fa.floor_number))
        capacity = floor_obj.total_seats if floor_obj else 0
        fill = round(fa.seats_assigned / capacity * 100, 1) if capacity > 0 else 0.0
        rows.append({
            "Unit": fa.unit_name,
            "Tower": fa.tower_id,
            "Floor": fa.floor_number,
            "Seats Assigned": fa.seats_assigned,
            "Floor Capacity": capacity,
            "Fill %": fill,
        })
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(
        columns=["Unit", "Tower", "Floor", "Seats Assigned", "Floor Capacity", "Fill %"]
    )


def _df_to_assignments(df: pd.DataFrame, raw_floors) -> List[FloorAssignment]:
    """Convert editor DataFrame back to FloorAssignment list."""
    lookup = _floor_lookup(raw_floors)
    assignments = []
    for _, row in df.iterrows():
        tower = str(row["Tower"]).strip()
        try:
            floor_num = int(row["Floor"])
            seats = max(0, int(row["Seats Assigned"]))
        except (ValueError, TypeError):
            continue
        floor_obj = lookup.get((tower, floor_num))
        assignments.append(FloorAssignment(
            unit_name=str(row["Unit"]).strip(),
            building_id=floor_obj.building_id if floor_obj else "",
            tower_id=tower,
            floor_number=floor_num,
            seats_assigned=seats,
            adjacency_tier="custom",
        ))
    return assignments


def _floor_utilization_table(assignments: List[FloorAssignment], raw_floors):
    """Compact per-floor utilization table below the editor."""
    if not assignments:
        return
    lookup = _floor_lookup(raw_floors)
    usage: dict = {}
    for fa in assignments:
        key = (fa.tower_id, fa.floor_number)
        usage[key] = usage.get(key, 0) + fa.seats_assigned

    rows = []
    for (tower, floor_num), used in sorted(usage.items()):
        floor_obj = lookup.get((tower, floor_num))
        capacity = floor_obj.total_seats if floor_obj else 0
        fill_pct = used / capacity if capacity > 0 else 0.0
        status = "Over capacity" if fill_pct > 1.0 else ("Near capacity" if fill_pct > 0.85 else "OK")
        rows.append({
            "Floor": f"{tower}-F{floor_num}",
            "Used": used,
            "Capacity": capacity,
            "Fill %": f"{fill_pct:.0%}",
            "Status": status,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render(sidebar_state):
    """Render the Floor Plan Sandbox tab."""
    st.header("Floor Plan Sandbox")
    st.caption(
        "Import an existing seating layout, make surgical edits — add floors, remove floors, "
        "move units — and instantly simulate the demand impact before committing to your scenario."
    )

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario:
        st.info("No active scenario found. Load data in the Admin tab first.")
        return

    raw_floors = get_floors()
    units = get_units()
    unit_names = sorted(u.unit_name for u in units)
    tower_ids = sorted(set(f.tower_id for f in raw_floors))
    floor_lookup = _floor_lookup(raw_floors)

    # =========================================================================
    # SECTION 1: Load a Plan
    # =========================================================================
    st.subheader("1. Load a Floor Plan")

    imp_c1, imp_c2 = st.columns([2, 1])
    with imp_c1:
        uploaded = st.file_uploader(
            "Upload Excel (.xlsx) or CSV with columns: Unit | Tower | Floor | Seats Assigned",
            type=["xlsx", "csv"],
            key="sandbox_file_uploader",
        )
    with imp_c2:
        st.markdown("<br>", unsafe_allow_html=True)
        has_assignments = bool(scenario.floor_assignments)
        load_from_scenario = st.button(
            "Load from Current Scenario",
            key="sandbox_load_scenario",
            help="Copy the active scenario's current floor assignments into the sandbox.",
            disabled=not has_assignments,
        )
        if not has_assignments:
            st.caption("Run a Policy Simulation first to populate assignments.")

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded)
            else:
                xl = pd.ExcelFile(uploaded)
                sheet = next(
                    (s for s in xl.sheet_names
                     if "floor" in s.lower() and "assign" in s.lower()),
                    xl.sheet_names[0],
                )
                df_upload = xl.parse(sheet)

            parsed = _parse_plan_upload(df_upload, raw_floors)
            st.session_state["sandbox_assignments"] = parsed
            st.session_state["sandbox_baseline_label"] = f"Imported: {uploaded.name}"
            st.session_state.pop("sandbox_impact_result", None)
            n_floors = len(set((fa.tower_id, fa.floor_number) for fa in parsed))
            st.success(
                f"Loaded **{len(parsed)} assignment rows** across **{n_floors} floors** "
                f"from '{uploaded.name}'."
            )
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Failed to parse file: {e}")

    if load_from_scenario:
        st.session_state["sandbox_assignments"] = _copy.deepcopy(scenario.floor_assignments)
        st.session_state["sandbox_baseline_label"] = f"Loaded from scenario: '{scenario.name}'"
        st.session_state.pop("sandbox_impact_result", None)
        st.rerun()

    baseline_label = st.session_state.get("sandbox_baseline_label", "")
    sandbox = st.session_state.get("sandbox_assignments", [])

    if baseline_label and sandbox:
        st.caption(f"Active sandbox: **{baseline_label}** — {len(sandbox)} row(s)")

    if not sandbox:
        st.info("Upload a plan or load from the current scenario to start editing.")
        return

    st.divider()

    # =========================================================================
    # SECTION 2: Assignment Editor
    # =========================================================================
    st.subheader("2. Edit Assignments")
    st.caption(
        "Edit the table directly **or** use the Quick Actions below. "
        "Quick Actions read your table edits before applying, so your manual changes are preserved."
    )

    editor_df = _assignments_to_df(sandbox, raw_floors)

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        num_rows="dynamic",
        key="sandbox_editor",
        column_config={
            "Unit": st.column_config.TextColumn("Unit"),
            "Tower": st.column_config.SelectboxColumn("Tower", options=tower_ids),
            "Floor": st.column_config.NumberColumn("Floor", min_value=1, max_value=99, step=1),
            "Seats Assigned": st.column_config.NumberColumn(
                "Seats Assigned", min_value=0, max_value=5000, step=1
            ),
            "Floor Capacity": st.column_config.NumberColumn("Capacity", disabled=True),
            "Fill %": st.column_config.NumberColumn("Fill %", disabled=True, format="%.1f%%"),
        },
    )

    # ── Quick Actions ────────────────────────────────────────────────────────
    st.markdown("**Quick Actions**")
    qa1, qa2 = st.columns(2)

    def _current() -> List[FloorAssignment]:
        """Read latest state from the edited table."""
        return _df_to_assignments(edited_df, raw_floors)

    with qa1:
        with st.expander("Move a Unit to a Different Floor"):
            mv_unit = st.selectbox("Unit to move", unit_names, key="mv_unit")
            unit_floor_ids = sorted(set(
                f"{fa.tower_id}-F{fa.floor_number}"
                for fa in _current() if fa.unit_name == mv_unit
            ))
            mv_from = st.selectbox(
                "From floor", unit_floor_ids or ["(none)"], key="mv_from",
            )
            mv_to = st.selectbox(
                "To floor",
                [f"{f.tower_id}-F{f.floor_number}" for f in raw_floors],
                key="mv_to",
            )
            if st.button("Apply Move", key="btn_mv"):
                if mv_from == "(none)":
                    st.warning("This unit has no assignments in the sandbox.")
                elif mv_from == mv_to:
                    st.warning("Source and target floors are the same.")
                else:
                    to_tower, to_fl = mv_to.rsplit("-F", 1)
                    to_fl_num = int(to_fl)
                    to_floor_obj = floor_lookup.get((to_tower, to_fl_num))
                    updated = _current()
                    for fa in updated:
                        if fa.unit_name == mv_unit and f"{fa.tower_id}-F{fa.floor_number}" == mv_from:
                            fa.tower_id = to_tower
                            fa.floor_number = to_fl_num
                            fa.building_id = to_floor_obj.building_id if to_floor_obj else fa.building_id
                            fa.adjacency_tier = "custom"
                    st.session_state["sandbox_assignments"] = updated
                    st.session_state.pop("sandbox_impact_result", None)
                    st.rerun()

        with st.expander("Remove All Assignments on a Floor"):
            occupied_floors = sorted(set(
                f"{fa.tower_id}-F{fa.floor_number}" for fa in _current()
            ))
            rm_floor = st.selectbox(
                "Floor to clear", occupied_floors or ["(none)"], key="rm_floor"
            )
            st.caption("All unit assignments on this floor will be removed from the sandbox.")
            if st.button("Remove Floor", key="btn_rm", type="secondary"):
                if rm_floor == "(none)":
                    st.warning("No floors in sandbox.")
                else:
                    rm_tower, rm_fl = rm_floor.rsplit("-F", 1)
                    rm_fl_num = int(rm_fl)
                    updated = [
                        fa for fa in _current()
                        if not (fa.tower_id == rm_tower and fa.floor_number == rm_fl_num)
                    ]
                    st.session_state["sandbox_assignments"] = updated
                    st.session_state.pop("sandbox_impact_result", None)
                    st.rerun()

    with qa2:
        with st.expander("Add a Unit to a Floor"):
            add_unit = st.selectbox("Unit", unit_names, key="add_unit")
            add_floor = st.selectbox(
                "Floor to assign",
                [f"{f.tower_id}-F{f.floor_number}" for f in raw_floors],
                key="add_floor",
            )
            add_seats = st.number_input(
                "Seats to assign", min_value=1, max_value=2000, value=50, step=10, key="add_seats"
            )
            if st.button("Add Assignment", key="btn_add"):
                add_tower, add_fl = add_floor.rsplit("-F", 1)
                add_fl_num = int(add_fl)
                add_floor_obj = floor_lookup.get((add_tower, add_fl_num))
                updated = _current()
                updated.append(FloorAssignment(
                    unit_name=add_unit,
                    building_id=add_floor_obj.building_id if add_floor_obj else "",
                    tower_id=add_tower,
                    floor_number=add_fl_num,
                    seats_assigned=int(add_seats),
                    adjacency_tier="custom",
                ))
                st.session_state["sandbox_assignments"] = updated
                st.session_state.pop("sandbox_impact_result", None)
                st.rerun()

        with st.expander("Resize a Unit's Seats on a Floor"):
            rs_unit = st.selectbox("Unit", unit_names, key="rs_unit")
            rs_unit_floors = sorted(set(
                f"{fa.tower_id}-F{fa.floor_number}"
                for fa in _current() if fa.unit_name == rs_unit
            ))
            rs_floor = st.selectbox("Floor", rs_unit_floors or ["(none)"], key="rs_floor")
            rs_seats = st.number_input(
                "New seat count", min_value=0, max_value=2000, value=50, step=10, key="rs_seats"
            )
            if st.button("Apply Resize", key="btn_rs"):
                if rs_floor == "(none)":
                    st.warning("This unit has no assignments in the sandbox.")
                else:
                    rs_tower, rs_fl = rs_floor.rsplit("-F", 1)
                    rs_fl_num = int(rs_fl)
                    updated = _current()
                    for fa in updated:
                        if (fa.unit_name == rs_unit
                                and fa.tower_id == rs_tower
                                and fa.floor_number == rs_fl_num):
                            fa.seats_assigned = int(rs_seats)
                    st.session_state["sandbox_assignments"] = updated
                    st.session_state.pop("sandbox_impact_result", None)
                    st.rerun()

    # Floor utilization summary
    with st.expander("Floor Utilization Summary", expanded=False):
        _floor_utilization_table(_current(), raw_floors)

    st.divider()

    # =========================================================================
    # SECTION 2.5: Additional Inputs
    # =========================================================================
    st.markdown("**Additional Inputs**")
    sandbox_cluster_map = get_cluster_map()
    use_cluster_diversity_sb = False
    if sandbox_cluster_map:
        use_cluster_diversity_sb = st.checkbox(
            "Apply Cluster-Diverse Floor Placement",
            value=False,
            key="sb_cluster_diversity",
            help=(
                "When enabled, Run Impact Analysis will re-assign seats using cluster-diverse placement "
                "(units from different attendance groups prefer to share a floor) "
                "instead of your sandbox layout. "
                "Useful to quickly compare your manual layout against the cluster-optimised alternative."
            ),
        )
        # Show cluster summary
        from collections import Counter as _Counter
        _cid_counts = _Counter(sandbox_cluster_map.values())
        _group_summary = " · ".join(
            f"Group {cid + 1}: {cnt} unit{'s' if cnt != 1 else ''}"
            for cid, cnt in sorted(_cid_counts.items())
        )
        st.caption(f"Cluster data available — {_group_summary}")
    else:
        st.caption(
            "ℹ️ Cluster-Diverse Placement unavailable — "
            "compute Temporal Clusters in Demand Analytics (or load sample data from Admin) first."
        )

    st.divider()

    # =========================================================================
    # SECTION 3: Simulate Impact
    # =========================================================================
    st.subheader("3. Simulate Impact")
    if use_cluster_diversity_sb:
        st.caption(
            "Cluster-Diverse Placement is **ON** — impact analysis will use a cluster-diverse "
            "floor assignment instead of your sandbox layout, so you can compare both approaches."
        )
    else:
        st.caption(
            "Runs the demand engine to compute seat needs, then compares against your sandbox layout."
        )

    sim_c1, sim_c2 = st.columns([1, 1])
    with sim_c1:
        run_sim = st.button("Run Impact Analysis", type="primary", key="btn_sandbox_sim")
    with sim_c2:
        run_reopt = st.button(
            "Re-Optimize Placement (LP)",
            key="btn_sandbox_reopt",
            help=(
                "Uses the LP optimizer to find the best floor assignments "
                "for the current demand. Updates the sandbox with the result."
            ),
        )

    if run_sim or run_reopt:
        current_sandbox = _current()
        if not current_sandbox:
            st.warning("Sandbox is empty — add at least one assignment before simulating.")
        else:
            with st.spinner("Running impact simulation..."):
                att_map = {a.unit_name: a for a in get_attendance()}
                rule_config = get_rule_config()

                # Build rule_config with cluster diversity if enabled
                if use_cluster_diversity_sb and sandbox_cluster_map:
                    rule_config = dict(rule_config)
                    rule_config["cluster_map"] = sandbox_cluster_map

                # Run demand engine on a temp copy
                temp_scenario = _copy.deepcopy(scenario)
                temp_scenario = run_scenario(
                    temp_scenario, units, att_map, raw_floors, rule_config
                )

                # Floor assignments: use cluster-diverse result from run_scenario, or sandbox layout
                if use_cluster_diversity_sb and sandbox_cluster_map:
                    # run_scenario already called assign_units_to_floors with cluster_map
                    # — keep those assignments (don't override with sandbox)
                    pass
                else:
                    # Replace run_scenario's assignments with sandbox layout
                    temp_scenario.floor_assignments = current_sandbox

                if run_reopt:
                    from engine.optimizer import optimize_allocation
                    eff_floors = apply_floor_modifications(raw_floors, temp_scenario)
                    _, temp_att_map = apply_overrides(units, att_map, temp_scenario)
                    opt_result = optimize_allocation(
                        allocations=temp_scenario.allocation_results,
                        floors=eff_floors,
                        baseline_assignments=current_sandbox,
                        objective="optimal_placement",
                        excluded_floor_ids=[],
                        units=units,
                        attendance_map=temp_att_map,
                        rule_config=rule_config,
                        max_floors_per_unit=3,
                        min_guarantee_pct=0.80,
                    )
                    if opt_result.assignments:
                        temp_scenario.floor_assignments = opt_result.assignments
                        # Sync optimized assignments back to sandbox
                        st.session_state["sandbox_assignments"] = opt_result.assignments
                        st.success(
                            f"Re-optimization complete ({opt_result.status}). "
                            "Sandbox updated with optimized assignments."
                        )
                    else:
                        st.error(f"Optimizer returned no assignments: {opt_result.status}")

                st.session_state["sandbox_impact_result"] = temp_scenario

    # ── Impact Results ───────────────────────────────────────────────────────
    impact = st.session_state.get("sandbox_impact_result")
    if impact and impact.allocation_results:
        st.markdown("---")
        st.markdown("**Impact Analysis Results**")

        # Compute seats per unit from the impact scenario's assignments
        sandbox_seats_by_unit: dict = {}
        for fa in impact.floor_assignments:
            sandbox_seats_by_unit[fa.unit_name] = (
                sandbox_seats_by_unit.get(fa.unit_name, 0) + fa.seats_assigned
            )

        total_demand = sum(a.effective_demand_seats for a in impact.allocation_results)
        total_sandbox = sum(sandbox_seats_by_unit.values())
        total_capacity = sum(f.total_seats for f in raw_floors)
        headroom = total_sandbox - total_demand

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Demand (Policy)", f"{total_demand:,}")
        m2.metric("Seats in Sandbox Plan", f"{total_sandbox:,}")
        m3.metric(
            "Headroom vs Demand",
            f"{headroom:+,}",
            delta_color="normal" if headroom >= 0 else "inverse",
        )
        m4.metric("Total Building Capacity", f"{total_capacity:,}")

        if headroom < 0:
            st.error(
                f"Sandbox plan has a **{abs(headroom):,} seat shortfall** vs. policy demand."
            )
        elif headroom < total_demand * 0.05:
            st.warning("Sandbox plan is very tight — less than 5% headroom above demand.")
        else:
            st.success("Sandbox plan covers all demand with adequate headroom.")

        # Per-unit breakdown
        st.markdown("**Per-Unit: Demand vs Sandbox Allocation**")
        unit_rows = []
        for alloc in impact.allocation_results:
            sb_seats = sandbox_seats_by_unit.get(alloc.unit_name, 0)
            gap = sb_seats - alloc.effective_demand_seats
            gap_pct = gap / alloc.effective_demand_seats if alloc.effective_demand_seats > 0 else 0
            if gap_pct < RISK_RED_GAP_PCT:
                risk = "RED"
            elif gap_pct < RISK_AMBER_GAP_PCT:
                risk = "AMBER"
            else:
                risk = "OK"
            unit_rows.append({
                "Unit": alloc.unit_name,
                "Demand (Policy)": alloc.effective_demand_seats,
                "Seats in Plan": sb_seats,
                "Gap": gap,
                "Gap %": f"{gap_pct:+.1%}",
                "Risk": risk,
            })
        st.dataframe(pd.DataFrame(unit_rows), use_container_width=True, hide_index=True)

        # Floor assignment detail
        with st.expander("Floor Assignment Detail", expanded=False):
            fa_rows = []
            for fa in sorted(
                impact.floor_assignments,
                key=lambda x: (x.tower_id, x.floor_number, x.unit_name),
            ):
                fl_obj = floor_lookup.get((fa.tower_id, fa.floor_number))
                capacity = fl_obj.total_seats if fl_obj else 0
                fa_rows.append({
                    "Unit": fa.unit_name,
                    "Tower": fa.tower_id,
                    "Floor": fa.floor_number,
                    "Seats Assigned": fa.seats_assigned,
                    "Capacity": capacity,
                    "Fill %": f"{fa.seats_assigned / capacity:.0%}" if capacity > 0 else "N/A",
                })
            if fa_rows:
                st.dataframe(pd.DataFrame(fa_rows), use_container_width=True, hide_index=True)

        # ── Download Report ──────────────────────────────────────────────────
        with st.expander("Download Sandbox Report", expanded=False):
            from datetime import date as _date
            from engine.report_generator import generate_scenario_report
            from engine.pdf_report_generator import generate_pdf_report
            from data.session_store import get_daily_attendance_df

            _daily_df = get_daily_attendance_df()
            _matrix = st.session_state.get("cmp_matrix_results")
            _att_rpt = {a.unit_name: a for a in get_attendance()}

            # Build a report-ready copy: impact's fresh demand + sandbox floor assignments
            _report_scenario = _copy.deepcopy(impact)
            for _alloc in _report_scenario.allocation_results:
                _alloc.allocated_seats = sandbox_seats_by_unit.get(
                    _alloc.unit_name, _alloc.allocated_seats
                )
                _alloc.seat_gap = _alloc.allocated_seats - _alloc.effective_demand_seats

            st.caption(
                "Report reflects the sandbox plan — demand from the policy engine, "
                "floor assignments from your edits."
            )
            _xlsx = generate_scenario_report(
                scenario=_report_scenario,
                floors=raw_floors,
                units=units,
                attendance_map=_att_rpt,
                rule_config=get_rule_config(),
                daily_attendance_df=_daily_df,
                matrix_results=_matrix,
            )
            st.download_button(
                label="Download Sandbox Report (.xlsx)",
                data=_xlsx,
                file_name=f"sandbox_{scenario.name.replace(' ', '_')}_{_date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_sandbox_dl_xlsx",
            )
            _pdf = generate_pdf_report(
                scenario=_report_scenario,
                floors=raw_floors,
                units=units,
                attendance_map=_att_rpt,
                rule_config=get_rule_config(),
                daily_attendance_df=_daily_df,
                matrix_results=_matrix,
            )
            st.download_button(
                label="Download Boardroom Report (.pdf)",
                data=_pdf,
                file_name=f"sandbox_{scenario.name.replace(' ', '_')}_{_date.today()}.pdf",
                mime="application/pdf",
                key="btn_sandbox_dl_pdf",
            )

        # Accept & Push
        st.divider()
        if not scenario.is_locked:
            st.markdown("**Accept this plan?**")
            st.caption(
                "Replaces the active scenario's floor assignments with your sandbox plan. "
                "All tabs (Dashboard, Spatial View, Unit Impact) will reflect the change."
            )
            if st.button(
                "Accept & Push to Active Scenario",
                type="primary",
                key="btn_sandbox_accept",
            ):
                # Use impact as the base — it has fresh allocation_results from run_scenario()
                # so all tabs see correct demand data, not stale values from the original scenario
                final_scenario = _copy.deepcopy(impact)
                for alloc in final_scenario.allocation_results:
                    alloc.allocated_seats = sandbox_seats_by_unit.get(alloc.unit_name, 0)
                    alloc.seat_gap = alloc.allocated_seats - alloc.effective_demand_seats
                update_scenario(final_scenario)
                add_audit_entry(
                    "sandbox_accept",
                    final_scenario.scenario_id,
                    "floor_assignments",
                    "previous",
                    f"sandbox plan ({len(final_scenario.floor_assignments)} assignments)",
                    rationale=(
                        f"Accepted from Floor Plan Sandbox — "
                        f"{st.session_state.get('sandbox_baseline_label', 'custom edit')}"
                    ),
                )
                # Clear sandbox state
                for key in ("sandbox_assignments", "sandbox_impact_result", "sandbox_baseline_label"):
                    st.session_state.pop(key, None)
                st.success(
                    "Sandbox plan accepted. Floor assignments updated — "
                    "Executive Dashboard, Spatial View, and Unit Impact now reflect the changes."
                )
                st.rerun()
        else:
            st.warning("Cannot accept — scenario is locked.")
