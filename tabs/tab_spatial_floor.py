"""Tab 3: Spatial / Floor View — operational and physical seat utilization."""

import streamlit as st
import pandas as pd

from data.session_store import get_active_scenario, get_floors, is_data_loaded
from engine.spatial import get_floor_utilization, get_consolidation_suggestions
from components.charts import floor_heatmap, unit_floor_heatmap
from components.floor_map import render_floor_map_grid
from config.defaults import FLOOR_SATURATION_THRESHOLD, FLOOR_SURPLUS_THRESHOLD


def render(sidebar_state):
    """Render the Spatial / Floor View tab."""
    st.header("Spatial / Floor View")

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario or not scenario.floor_assignments:
        st.info("No floor assignments available. Run a simulation from the Scenario Lab.")
        return

    floors = get_floors()
    assignments = scenario.floor_assignments
    allocations = scenario.allocation_results

    # Floor utilization data
    floor_util = get_floor_utilization(floors, assignments)

    # --- Tower Selector ---
    towers = sorted(set(f.tower_id for f in floors))
    selected_tower = st.selectbox("Filter by Tower", ["All"] + towers, key="spatial_tower")

    tower_filter = selected_tower if selected_tower != "All" else None

    # --- View Mode Toggle ---
    view_mode = st.radio(
        "View Mode",
        ["Charts", "Floor Map"],
        horizontal=True,
        key="spatial_view_mode",
    )

    if view_mode == "Floor Map":
        # --- Floor Map View ---
        st.subheader("Floor Allocation Map")
        st.caption("Each block represents a unit's seat allocation on the floor. Grey = available capacity.")

        # Build per-floor assignment data
        floor_map_data = {}
        floor_lookup = {f.floor_id: f for f in floors}
        for a in assignments:
            fid = f"{a.tower_id}-F{a.floor_number}"
            if tower_filter and not fid.startswith(tower_filter):
                continue
            if fid not in floor_map_data:
                f_obj = floor_lookup.get(fid)
                floor_map_data[fid] = {
                    "total_seats": f_obj.total_seats if f_obj else 0,
                    "assignments": [],
                }
            floor_map_data[fid]["assignments"].append({
                "unit_name": a.unit_name,
                "seats_assigned": a.seats_assigned,
            })

        if floor_map_data:
            render_floor_map_grid(floor_map_data, columns=2)
        else:
            st.info("No floor assignments to display.")

    else:
        # --- Chart View (existing) ---
        col1, col2 = st.columns([3, 2])

        with col1:
            fig = floor_heatmap(floor_util, tower_filter)
            st.plotly_chart(fig, use_container_width=True, key="spatial_floor_heatmap")

        with col2:
            # Summary stats
            filtered_util = floor_util
            if tower_filter:
                filtered_util = [f for f in floor_util if f["tower_id"] == tower_filter]

            total = sum(f["total_seats"] for f in filtered_util)
            used = sum(f["used_seats"] for f in filtered_util)

            st.metric("Total Seats", f"{total:,}")
            st.metric("Used Seats", f"{used:,}")
            st.metric("Utilization", f"{used/total:.1%}" if total > 0 else "N/A")

            saturated = sum(1 for f in filtered_util if f["utilization_pct"] > FLOOR_SATURATION_THRESHOLD)
            surplus = sum(1 for f in filtered_util if f["utilization_pct"] < FLOOR_SURPLUS_THRESHOLD)
            st.metric("Saturated Floors (>90%)", saturated)
            st.metric("Surplus Floors (<80%)", surplus)

        st.divider()

        # --- Unit x Floor Heatmap ---
        st.subheader("Unit Distribution by Floor")

        # Prepare assignment data for heatmap
        assignment_dicts = [{
            "tower_id": a.tower_id,
            "floor_number": a.floor_number,
            "unit_name": a.unit_name,
            "seats_assigned": a.seats_assigned,
        } for a in assignments]

        floor_ids = sorted(set(f.floor_id for f in floors))
        unit_names = sorted(set(a.unit_name for a in assignments))

        if tower_filter:
            floor_ids = [fid for fid in floor_ids if fid.startswith(tower_filter)]
            assignment_dicts = [a for a in assignment_dicts if a["tower_id"] == tower_filter]

        if assignment_dicts and floor_ids and unit_names:
            fig = unit_floor_heatmap(assignment_dicts, floor_ids, unit_names)
            st.plotly_chart(fig, use_container_width=True, key="spatial_unit_heatmap")

    st.divider()

    # --- Floor Detail Table ---
    st.subheader("Floor Detail")
    detail_rows = []
    for fu in floor_util:
        if tower_filter and fu["tower_id"] != tower_filter:
            continue
        largest_unit = max(fu["units"], key=fu["units"].get) if fu["units"] else "—"
        largest_seats = fu["units"].get(largest_unit, 0) if fu["units"] else 0
        largest_str = f"{largest_unit} ({largest_seats})" if largest_unit != "—" else "—"
        detail_rows.append({
            "Floor": fu["floor_id"],
            "Building": fu["building_name"],
            "Tower": fu["tower_id"],
            "Floor #": fu["floor_number"],
            "Total Seats": fu["total_seats"],
            "Used": fu["used_seats"],
            "Available": fu["available_seats"],
            "Utilization": f"{fu['utilization_pct']:.0%}",
            "# Units": fu["unit_count"],
            "Largest Unit": largest_str,
        })

    if detail_rows:
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, height=400)

    st.divider()

    # --- Cross-Building Spread ---
    st.subheader("Building Spread")
    from collections import defaultdict
    unit_bldg_spread = defaultdict(lambda: defaultdict(int))
    for a in assignments:
        unit_bldg_spread[a.unit_name][a.building_id] += 1

    cross_bldg_units = {u: b for u, b in unit_bldg_spread.items() if len(b) > 1}
    if cross_bldg_units:
        for unit_name, bldgs in sorted(cross_bldg_units.items()):
            detail = ", ".join(f"{bid} ({cnt} floor{'s' if cnt > 1 else ''})"
                               for bid, cnt in sorted(bldgs.items()))
            st.warning(f"**{unit_name}**: spread across {len(bldgs)} buildings — {detail}")
    else:
        st.success("All units are contained within a single building.")

    st.divider()

    # --- Consolidation Suggestions ---
    st.subheader("Consolidation Suggestions")
    frag_scores = {a.unit_name: a.fragmentation_score for a in allocations}
    suggestions = get_consolidation_suggestions(allocations, assignments, frag_scores)

    if suggestions:
        for s in suggestions:
            st.warning(s)
    else:
        st.success("No consolidation opportunities identified — fragmentation is acceptable.")

    st.divider()

    # --- Co-location Recommendations (AI) ---
    with st.expander("Co-location Recommendations", expanded=False):
        st.caption(
            "Suggests which units are best suited to share a floor based on "
            "similarity in team size, growth rate, shift patterns, RTO frequency, "
            "and business priority. Higher score = better co-location fit."
        )

        from engine.colocation import (
            compute_colocation_scores, get_current_colocations,
            flag_colocation_mismatches,
        )
        from data.session_store import get_units, get_attendance
        from components.charts import colocation_heatmap

        units_for_coloc = get_units()
        att_profiles = get_attendance()
        att_map_coloc = {a.unit_name: a for a in att_profiles}

        if len(units_for_coloc) < 2:
            st.info("Need at least 2 units to compute co-location scores.")
        else:
            scores = compute_colocation_scores(units_for_coloc, att_map_coloc)

            if scores:
                fig = colocation_heatmap(scores)
                st.plotly_chart(fig, use_container_width=True, key="spatial_coloc_heatmap")

                st.markdown("**Top Co-location Pairs:**")
                pair_rows = []
                for s in scores[:10]:
                    pair_rows.append({
                        "Unit A": s["unit_a"],
                        "Unit B": s["unit_b"],
                        "Score": f"{s['score']:.0%}",
                        "Reasoning": s["reasoning"],
                    })
                st.dataframe(pd.DataFrame(pair_rows), use_container_width=True,
                             hide_index=True)

            current = get_current_colocations(assignments)
            if current:
                st.markdown("**Currently Co-located Units:**")
                for c in current:
                    st.markdown(
                        f"- **{c['floor_id']}**: {', '.join(c['units'])} "
                        f"({c['unit_count']} units)"
                    )

                if scores:
                    mismatches = flag_colocation_mismatches(current, scores)
                    if mismatches:
                        st.markdown("**Mismatch Alerts:**")
                        for m in mismatches:
                            st.warning(
                                f"**{m['floor_id']}**: {m['unit_a']} + {m['unit_b']} "
                                f"(affinity {m['score']:.0%}) — {m['flag_reason']}"
                            )
