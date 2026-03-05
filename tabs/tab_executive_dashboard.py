"""Tab 1: Executive Dashboard — high-level planning health and feasibility."""

import streamlit as st
import pandas as pd

from data.session_store import (
    get_active_scenario, get_floors, get_units, get_attendance,
    get_rule_config, is_data_loaded, get_last_data_edit,
)
from components.metrics_cards import render_metric_row
from components.charts import capacity_vs_demand_bar, utilization_donut, rto_need_vs_allocated_bar
from engine.spatial import get_floor_utilization
from engine.allocation_engine import compute_rto_alerts
from engine.scenario_engine import apply_floor_modifications, apply_overrides
from config.defaults import FLOOR_SATURATION_THRESHOLD, UNIT_SHORTFALL_THRESHOLD


def _generate_insights(allocs, floors, rto_alert_map, scenario, rule_config):
    """Return a list of rule-based insight dicts with keys 'type' and 'text'.
    Types: 'risk' | 'opportunity' | 'neutral'
    """
    insights = []

    # 1. Most critical seat shortfall
    shortfalls = [(a.unit_name, a.seat_gap) for a in allocs if a.seat_gap < 0]
    if shortfalls:
        worst = min(shortfalls, key=lambda x: x[1])
        insights.append({
            "type": "risk",
            "text": (f"**{worst[0]}** has the largest seat shortfall: **{worst[1]:+d} seats**. "
                     "Run Optimization → RTO-Based to reclaim unused supply."),
        })

    # 2. Best consolidation opportunity (highest fragmentation > 0.5)
    frag_units = [(a.unit_name, a.fragmentation_score)
                  for a in allocs if a.fragmentation_score > 0.5]
    if frag_units:
        top_frag = max(frag_units, key=lambda x: x[1])
        insights.append({
            "type": "opportunity",
            "text": (f"**{top_frag[0]}** is spread across multiple floors "
                     f"(fragmentation score **{top_frag[1]:.2f}**). "
                     "Consolidating to fewer floors could free real estate."),
        })

    # 3. Most over-provisioned unit vs RTO need
    over = []
    for a in allocs:
        ra = rto_alert_map.get(a.unit_name)
        if ra and a.allocated_seats > ra["expected_seats"]:
            excess = a.allocated_seats - ra["expected_seats"]
            over.append((a.unit_name, excess, ra["expected_seats"]))
    if over:
        top_over = max(over, key=lambda x: x[1])
        insights.append({
            "type": "opportunity",
            "text": (f"**{top_over[0]}** is over-provisioned by **{top_over[1]:+d} seats** "
                     f"vs attendance need (RTO need: {top_over[2]} seats). "
                     "Reallocating this surplus could resolve a shortfall elsewhere."),
        })

    # 4. Floors below 40% utilization
    low_util = [f for f in floors
                if f.total_seats > 0
                and hasattr(f, "assigned_seats")
                and 0 < f.assigned_seats / f.total_seats < 0.40]
    if low_util:
        insights.append({
            "type": "opportunity",
            "text": (f"**{len(low_util)} floor(s)** are below 40% utilization. "
                     "Consolidating occupants onto fewer floors could free entire floors for sublease."),
        })

    # 5. Potential saving from RTO-based optimization
    total_alloc = sum(a.allocated_seats for a in allocs)
    total_rto_need = sum(rto_alert_map[a.unit_name]["expected_seats"]
                         for a in allocs if a.unit_name in rto_alert_map)
    potential_saving = total_alloc - total_rto_need
    if potential_saving > 0 and total_alloc > 0:
        insights.append({
            "type": "neutral",
            "text": (f"RTO-Based Optimization could reduce seat demand by up to "
                     f"**{potential_saving:,} seats** "
                     f"(**{potential_saving / total_alloc:.0%}** of current allocation). "
                     "Run the Optimization tab to see floor-level savings."),
        })

    return insights


def _render_key_insights(allocs, floors, scenario, rule_config):
    """Render the Key Insights strip on the Executive Dashboard."""
    from engine.allocation_engine import compute_rto_alerts
    from engine.scenario_engine import apply_overrides
    from data.session_store import get_units, get_attendance

    units = get_units()
    att_profiles = get_attendance()
    att_map = {a.unit_name: a for a in att_profiles}
    _, scenario_att_map = apply_overrides(units, att_map, scenario)
    rto_data = compute_rto_alerts(allocs, units, scenario_att_map, rule_config)
    rto_alert_map = {ra["unit_name"]: ra for ra in rto_data}

    insights = _generate_insights(allocs, floors, rto_alert_map, scenario, rule_config)
    if not insights:
        return

    st.subheader("Key Insights")
    for ins in insights:
        if ins["type"] == "risk":
            st.warning(f"🔴 {ins['text']}")
        elif ins["type"] == "opportunity":
            st.info(f"💡 {ins['text']}")
        else:
            st.success(f"📊 {ins['text']}")
    st.divider()


def render(sidebar_state):
    """Render the Executive Dashboard tab."""
    st.header("Executive Dashboard")

    if not is_data_loaded():
        st.info("No data loaded. Please upload data in the Admin & Governance tab.")
        return

    scenario = get_active_scenario()
    if not scenario or not scenario.allocation_results:
        st.info("No allocation results available. Run a simulation from the Scenario Lab.")
        return

    # Stale-data warning
    last_edit = get_last_data_edit()
    if last_edit and (scenario.last_run_at is None or last_edit > scenario.last_run_at):
        st.warning(
            "Base data has changed since the last simulation. "
            "Go to Scenario Lab and re-run to see updated results."
        )

    allocations = scenario.allocation_results
    assignments = scenario.floor_assignments
    floors = get_floors()

    # Compute effective supply (accounting for scenario exclusions + capacity reduction)
    effective_floors = apply_floor_modifications(floors, scenario)
    raw_total_seats = sum(f.total_seats for f in floors)
    effective_total_seats = sum(f.total_seats for f in effective_floors)
    has_scenario_adjustments = effective_total_seats < raw_total_seats

    # --- KPI Metrics ---
    total_demand = sum(a.effective_demand_seats for a in allocations)
    total_allocated = sum(a.allocated_seats for a in allocations)
    seat_gap = total_allocated - total_demand
    impacted_units = sum(1 for a in allocations if a.seat_gap < 0)

    supply_label = "Effective Supply" if has_scenario_adjustments else "Total Seats (Supply)"
    supply_metrics = {"label": supply_label, "value": f"{effective_total_seats:,}"}
    if has_scenario_adjustments:
        supply_metrics["delta"] = f"of {raw_total_seats:,} base seats"
        supply_metrics["delta_color"] = "off"

    render_metric_row([
        supply_metrics,
        {"label": "Total Demand", "value": f"{total_demand:,}"},
        {"label": "Seat Gap", "value": f"{seat_gap:+,}",
         "delta": f"{seat_gap:+,}", "delta_color": "normal" if seat_gap >= 0 else "inverse"},
        {"label": "Units with Shortfall", "value": str(impacted_units),
         "delta": f"{impacted_units} units" if impacted_units > 0 else "None",
         "delta_color": "inverse" if impacted_units > 0 else "normal"},
    ])

    # Hot-seating savings (if any unit has night shift)
    total_hot_savings = sum(a.hot_seat_savings for a in allocations)
    if total_hot_savings > 0:
        shift_units = sum(1 for a in allocations if a.hot_seat_savings > 0)
        st.info(
            f"**Hot-Seating Savings:** {total_hot_savings:,} seats saved via day/night desk sharing "
            f"across {shift_units} unit(s). Physical demand reduced from {total_demand:,} to "
            f"{total_demand - total_hot_savings:,} seats."
        )

    # Scenario context (always visible)
    st.caption(
        f"Active scenario: **{scenario.name}** · Type: {scenario.scenario_type} · "
        f"Horizon: {scenario.planning_horizon_months} months · "
        f"Last run: {scenario.last_run_at.strftime('%b %d, %H:%M') if scenario.last_run_at else 'Not yet run'}"
    )

    # Scenario adjustment info
    if has_scenario_adjustments:
        notes = []
        if scenario.params.excluded_floors:
            notes.append(f"{len(scenario.params.excluded_floors)} floors excluded ({', '.join(scenario.params.excluded_floors)})")
        if scenario.params.capacity_reduction_pct > 0:
            notes.append(f"{scenario.params.capacity_reduction_pct:.0%} capacity reduction applied")
        st.info(f"Scenario adjustments: {'; '.join(notes)}. "
                f"Effective supply is {effective_total_seats:,} seats (base: {raw_total_seats:,}).")

    st.divider()

    # --- Key Insights (rule-based, auto-generated from allocation data) ---
    _render_key_insights(allocations, floors, scenario, get_rule_config())

    # --- Charts ---
    col1, col2 = st.columns([3, 2])

    with col1:
        # Capacity vs demand by tower
        floor_util = get_floor_utilization(floors, assignments)
        tower_summary = {}
        for fu in floor_util:
            tid = fu["tower_id"]
            if tid not in tower_summary:
                tower_summary[tid] = {"tower_id": tid, "total_seats": 0, "used_seats": 0}
            tower_summary[tid]["total_seats"] += fu["total_seats"]
            tower_summary[tid]["used_seats"] += fu["used_seats"]

        fig = capacity_vs_demand_bar(list(tower_summary.values()))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = utilization_donut(total_allocated, effective_total_seats)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Alerts ---
    # Collect alerts by category
    capacity_alerts = []
    rto_alerts_list = []
    other_alerts = []

    # Floor saturation alerts
    for fu in floor_util:
        if fu["utilization_pct"] > FLOOR_SATURATION_THRESHOLD:
            capacity_alerts.append({
                "Floor": fu["floor_id"],
                "Status": "Saturated",
                "Used / Total": f"{fu['used_seats']} / {fu['total_seats']}",
                "Utilization": f"{fu['utilization_pct']:.0%}",
            })

    # Unit shortfall alerts
    for a in allocations:
        if a.effective_demand_seats > 0:
            gap_pct = a.seat_gap / a.effective_demand_seats
            if gap_pct < UNIT_SHORTFALL_THRESHOLD:
                capacity_alerts.append({
                    "Floor": a.unit_name,
                    "Status": "Shortfall",
                    "Used / Total": f"{a.allocated_seats} / {a.effective_demand_seats}",
                    "Utilization": f"{gap_pct:+.0%}",
                })

    # RTO compliance alerts (units below global RTO target)
    units = get_units()
    attendance_profiles = get_attendance()
    att_map = {a.unit_name: a for a in attendance_profiles}

    # RTO utilization data (use scenario-modified attendance for RTO mandate)
    _, scenario_att_map = apply_overrides(units, att_map, scenario)
    rto_alerts_data = compute_rto_alerts(allocations, units, scenario_att_map, get_rule_config())
    rto_chart_data = [ra for ra in rto_alerts_data if ra["status"] != "Aligned"]
    rto_all_data = rto_alerts_data  # all units for chart
    for ra in rto_chart_data:
        rto_alerts_list.append({
            "Unit": ra["unit_name"],
            "Alert": ra["status"],
            "Allocated": ra["allocated_seats"],
            "RTO Need": ra["expected_seats"],
        })

    # Fragmentation alerts
    for a in allocations:
        if a.fragmentation_score > 0.7:
            other_alerts.append({
                "Unit": a.unit_name,
                "Alert": "High Fragmentation",
                "Detail": f"Score: {a.fragmentation_score:.2f}",
            })

    # Cross-building spread alerts
    from collections import defaultdict
    unit_bldg_map = defaultdict(lambda: defaultdict(int))
    for a in assignments:
        unit_bldg_map[a.unit_name][a.building_id] += 1
    for unit_name, bldgs in unit_bldg_map.items():
        if len(bldgs) > 1:
            detail_parts = [f"{bid} ({cnt} floor{'s' if cnt > 1 else ''})"
                            for bid, cnt in sorted(bldgs.items())]
            other_alerts.append({
                "Unit": unit_name,
                "Alert": "Cross-Building Spread",
                "Detail": f"Across {', '.join(detail_parts)}",
            })

    # Attendance anomaly alerts
    from engine.anomaly import detect_attendance_anomalies, get_anomaly_summary
    att_map_anom = {a.unit_name: a for a in attendance_profiles}
    anomalies = detect_attendance_anomalies(units, att_map_anom)
    anomaly_summary = get_anomaly_summary(anomalies)

    for anom in anomalies:
        other_alerts.append({
            "Unit": anom["unit_name"],
            "Alert": f"Anomaly: {anom['anomaly_type']}",
            "Detail": f"Z-score: {anom['z_score']:+.2f} ({anom['metric']} = {anom['value']})",
        })

    has_any = capacity_alerts or rto_all_data or other_alerts

    st.subheader("Planning Alerts")

    if not has_any:
        st.success("No planning alerts — all metrics within acceptable ranges.")
    else:
        # --- Alert summary cards (3 columns, color-coded by type) ---
        cap_count = len(capacity_alerts)
        rto_count = len(rto_alerts_list)
        oth_count = len(other_alerts)

        card_css = (
            "padding:10px 14px;border-radius:6px;margin-bottom:6px;"
            "font-family:sans-serif;line-height:1.4;"
        )
        cap_bg  = "#FFCCCC" if cap_count  else "#F5F5F5"
        rto_bg  = "#FFF3CC" if rto_count  else "#F5F5F5"
        oth_bg  = "#E8E8E8" if oth_count  else "#F5F5F5"
        cap_bdr = "#CC0000" if cap_count  else "#BBBBBB"
        rto_bdr = "#BB7700" if rto_count  else "#BBBBBB"
        oth_bdr = "#666666" if oth_count  else "#BBBBBB"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f'<div style="{card_css}background:{cap_bg};border-left:4px solid {cap_bdr};">'
                f'<span style="font-size:1.25em;font-weight:700;">🔴 {cap_count}</span><br/>'
                f'<span style="font-size:0.78em;color:#444;">Capacity Alerts</span><br/>'
                f'<span style="font-size:0.72em;color:#666;">Floor saturation &amp; unit shortfalls</span>'
                f'</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div style="{card_css}background:{rto_bg};border-left:4px solid {rto_bdr};">'
                f'<span style="font-size:1.25em;font-weight:700;">🟡 {rto_count}</span><br/>'
                f'<span style="font-size:0.78em;color:#444;">RTO Alerts</span><br/>'
                f'<span style="font-size:0.72em;color:#666;">Allocation vs attendance-based need</span>'
                f'</div>', unsafe_allow_html=True)
        with c3:
            anom_count = anomaly_summary.get("total_anomalies", 0)
            anom_suffix = f" &amp; {anom_count} anomalies" if anom_count else ""
            st.markdown(
                f'<div style="{card_css}background:{oth_bg};border-left:4px solid {oth_bdr};">'
                f'<span style="font-size:1.25em;font-weight:700;">⚠️ {oth_count}</span><br/>'
                f'<span style="font-size:0.78em;color:#444;">Other Alerts</span><br/>'
                f'<span style="font-size:0.72em;color:#666;">Fragmentation, cross-building spread{anom_suffix}</span>'
                f'</div>', unsafe_allow_html=True)

        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

        # --- Capacity Alerts expander ---
        with st.expander(f"🔴 Capacity Alerts ({cap_count})", expanded=cap_count > 0):
            st.caption(
                "**What this measures:** seats allocated vs. seats demanded under the policy rule. "
                "A shortfall means a unit cannot be fully seated at the planned allocation level."
            )
            if capacity_alerts:
                st.dataframe(pd.DataFrame(capacity_alerts), use_container_width=True, hide_index=True)
            else:
                st.info("No capacity alerts.")

        # --- RTO Alerts expander ---
        with st.expander(f"🟡 RTO Alerts ({rto_count})", expanded=rto_count > 0):
            st.caption(
                "**What this measures:** allocated seats vs. attendance-based need "
                "(median HC + peak buffer × RTO days/week). "
                "Under-utilized = over-provisioned vs. real attendance. "
                "Under-allocated = attendance need exceeds what was assigned."
            )
            if rto_all_data:
                fig = rto_need_vs_allocated_bar(rto_all_data)
                st.plotly_chart(fig, use_container_width=True)
            if rto_alerts_list:
                st.warning(f"{rto_count} unit{'s' if rto_count != 1 else ''} with allocation vs attendance mismatch")
                st.dataframe(pd.DataFrame(rto_alerts_list), use_container_width=True, hide_index=True)

        # --- Other Alerts expander ---
        with st.expander(f"⚠️ Other Alerts ({oth_count})", expanded=False):
            st.caption(
                "**What this measures:** spatial efficiency issues — fragmentation (unit spread "
                "across too many floors) and cross-building spread (unit split across buildings)."
            )
            if other_alerts:
                st.dataframe(pd.DataFrame(other_alerts), use_container_width=True, hide_index=True)
            else:
                st.info("No other alerts.")

    # --- AI Executive Brief (hidden; only visible when GEMINI_API_KEY is set) ---
    from config.ai_config import is_ai_enabled, generate_executive_brief
    if is_ai_enabled():
        st.divider()
        with st.expander("AI Executive Brief (Gemini)", expanded=False):
            st.caption(
                "Auto-generated plain-English summary of this scenario for leadership. "
                "Powered by Google Gemini."
            )
            if st.button("Generate Brief", key="btn_ai_brief"):
                # Build the context summary for the AI prompt
                rto_need_total = sum(
                    ra["expected_seats"] for ra in rto_all_data
                ) if "rto_all_data" in dir() else 0
                potential_saving = max(0, total_allocated - rto_need_total)

                shortfalls = [(a.unit_name, a.seat_gap) for a in allocations if a.seat_gap < 0]
                top_risk_unit = min(shortfalls, key=lambda x: x[1]) if shortfalls else ("N/A", 0)

                over_prov = [
                    (ra["unit_name"], allocations[0].allocated_seats - ra["expected_seats"])
                    for ra in rto_all_data
                    if ra["status"] == "Under-utilized"
                ] if "rto_all_data" in dir() else []
                top_opp = (max(over_prov, key=lambda x: x[1])[0]
                           if over_prov else "No significant over-provisioning detected")

                red_count = sum(
                    1 for a in allocations
                    if (a.seat_gap / a.effective_demand_seats
                        if a.effective_demand_seats else 0) < -0.10
                    or a.fragmentation_score > 0.8
                )
                amber_count = sum(
                    1 for a in allocations
                    if (a.seat_gap / a.effective_demand_seats
                        if a.effective_demand_seats else 0) < -0.05
                    or a.fragmentation_score > 0.5
                ) - red_count

                summary = {
                    "scenario_name":   scenario.name,
                    "scenario_type":   scenario.scenario_type,
                    "horizon":         scenario.planning_horizon_months,
                    "total_supply":    effective_total_seats,
                    "total_demand":    total_demand,
                    "net_gap":         seat_gap,
                    "units_at_risk":   impacted_units,
                    "red_count":       max(0, red_count),
                    "amber_count":     max(0, amber_count),
                    "total_rto_need":  rto_need_total,
                    "potential_saving": potential_saving,
                    "top_risk_unit":   top_risk_unit[0],
                    "top_risk_gap":    top_risk_unit[1],
                    "top_opportunity": top_opp,
                }
                with st.spinner("Generating executive brief via Gemini..."):
                    brief = generate_executive_brief(summary)
                if brief:
                    st.markdown(brief)
                else:
                    st.warning("Could not generate brief. Check the GEMINI_API_KEY or try again.")
