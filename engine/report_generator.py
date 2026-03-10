"""Generate downloadable Excel reports from simulation and optimization results."""

import io
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from models.scenario import Scenario
from models.building import Floor
from models.unit import Unit
from models.attendance import AttendanceProfile
from engine.allocation_engine import compute_rto_alerts, compute_rto_compliance
from config.defaults import RISK_RED_GAP_PCT, RISK_AMBER_GAP_PCT, RISK_RED_FRAGMENTATION, RISK_AMBER_FRAGMENTATION


def _risk_level(gap_pct: float, frag: float) -> str:
    if gap_pct < RISK_RED_GAP_PCT or frag > RISK_RED_FRAGMENTATION:
        return "RED"
    if gap_pct < RISK_AMBER_GAP_PCT or frag > RISK_AMBER_FRAGMENTATION:
        return "AMBER"
    return "GREEN"


def generate_scenario_report(
    scenario: Scenario,
    floors: List[Floor],
    units: List[Unit],
    attendance_map: Dict[str, AttendanceProfile],
    rule_config: dict,
    opt_history: Optional[list] = None,
    daily_attendance_df=None,
    matrix_results: Optional[list] = None,
) -> bytes:
    """
    Build a multi-sheet Excel report for management review.

    Sheets:
    1. Summary — scenario parameters and high-level KPIs
    2. Allocation Results — per-unit allocation, demand, gap, risk, RTO
    3. Floor Assignments — where each unit is placed
    4. Risks & Alerts — capacity and RTO issues
    5. Optimization Run — most recent optimization result (if available)
    6. Demand Forecast — per-unit forecast summary (if daily_attendance_df provided)
    7. Scenario Comparison — ranked matrix run results (if matrix_results provided)

    Returns bytes suitable for st.download_button.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _write_summary(writer, scenario, floors, rule_config)
        _write_allocation_results(writer, scenario, units, attendance_map, rule_config)
        _write_floor_assignments(writer, scenario, floors)
        _write_risks_alerts(writer, scenario, units, attendance_map, rule_config)
        if opt_history:
            _write_optimization_run(writer, opt_history[0])
        if daily_attendance_df is not None:
            _write_demand_forecast(writer, daily_attendance_df)
        if matrix_results:
            _write_scenario_comparison(writer, matrix_results)

    return output.getvalue()


def _write_summary(writer, scenario: Scenario, floors: List[Floor], config: dict):
    total_supply = sum(f.total_seats for f in floors)
    total_demand = sum(a.effective_demand_seats for a in scenario.allocation_results) if scenario.allocation_results else 0
    total_allocated = sum(a.allocated_seats for a in scenario.allocation_results) if scenario.allocation_results else 0
    seat_gap = total_allocated - total_demand

    rows = [
        ["Scenario Name", scenario.name],
        ["Scenario Type", scenario.scenario_type],
        ["Planning Horizon (months)", scenario.planning_horizon_months],
        ["Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Last Simulation Run", scenario.last_run_at.strftime("%Y-%m-%d %H:%M") if scenario.last_run_at else "Not run"],
        ["", ""],
        ["--- Supply & Demand ---", ""],
        ["Total Physical Seat Supply", total_supply],
        ["Total Projected Demand", total_demand],
        ["Total Seats Allocated by Policy", total_allocated],
        ["Supply Headroom (Supply − Demand)", total_supply - total_demand],
        ["Allocation Gap (Allocated − Demand)", seat_gap],
        ["", ""],
        ["--- Scenario Parameters ---", ""],
        ["Global RTO Mandate (days/week)", scenario.params.global_rto_mandate_days or "None"],
        ["Excluded Floors", ", ".join(scenario.params.excluded_floors) if scenario.params.excluded_floors else "None"],
        ["Unit Overrides Applied", len(scenario.unit_overrides)],
        ["", ""],
        ["--- Rule Configuration ---", ""],
        ["Global Seat Allocation %", f"{config.get('global_alloc_pct', 0.80):.0%}"],
        ["Min Allocation %", f"{config.get('min_alloc_pct', 0.20):.0%}"],
        ["Max Allocation %", f"{config.get('max_alloc_pct', 1.50):.0%}"],
        ["Planning Buffer Level", config.get("planning_buffer_level", "balanced").capitalize()],
    ]
    df = pd.DataFrame(rows, columns=["Parameter", "Value"])
    df.to_excel(writer, sheet_name="Summary", index=False)


def _write_allocation_results(writer, scenario: Scenario, units: List[Unit],
                               attendance_map: Dict[str, AttendanceProfile], config: dict):
    if not scenario.allocation_results:
        pd.DataFrame([{"Note": "No simulation results available."}]).to_excel(
            writer, sheet_name="Allocation Results", index=False
        )
        return

    rto_alerts = compute_rto_alerts(scenario.allocation_results, units, attendance_map, config)
    rto_alert_map = {r["unit_name"]: r for r in rto_alerts}

    has_mandate = bool(scenario.params.global_rto_mandate_days)
    compliance_map = {}
    if has_mandate:
        compliance = compute_rto_compliance(attendance_map, scenario.params.global_rto_mandate_days)
        compliance_map = {r["unit_name"]: r for r in compliance}

    unit_map = {u.unit_name: u for u in units}
    rows = []
    for a in scenario.allocation_results:
        u = unit_map.get(a.unit_name)
        ra = rto_alert_map.get(a.unit_name)
        rc = compliance_map.get(a.unit_name)

        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
        risk = _risk_level(gap_pct, a.fragmentation_score)

        rto_need = ra["expected_seats"] if ra else "N/A"
        rto_status = ra["status"] if ra else "N/A"
        compliance_str = "N/A"
        if has_mandate and rc:
            compliance_str = f"{rc['actual_rto']:.1f} / {rc['target_rto']:.1f} {'✓' if rc['compliant'] else '✗'}"

        rows.append({
            "Unit": a.unit_name,
            "Priority": (u.business_priority or "—") if u else "—",
            "Current HC": u.current_total_hc if u else "—",
            "Growth %": f"{u.hc_growth_pct:.0%}" if u else "—",
            "Alloc %": f"{a.recommended_alloc_pct:.1%}",
            "Demand Seats": a.effective_demand_seats,
            "Allocated Seats": a.allocated_seats,
            "Gap": a.seat_gap,
            "Risk Level": risk,
            "RTO Need (seats)": rto_need,
            "RTO Utilization": rto_status,
            "RTO Compliance": compliance_str,
            "Fragmentation": f"{a.fragmentation_score:.2f}",
            "Overridden": "Yes" if a.is_overridden else "No",
        })

    pd.DataFrame(rows).to_excel(writer, sheet_name="Allocation Results", index=False)


def _write_floor_assignments(writer, scenario: Scenario, floors: List[Floor]):
    if not scenario.floor_assignments:
        pd.DataFrame([{"Note": "No floor assignments available. Run simulation first."}]).to_excel(
            writer, sheet_name="Floor Assignments", index=False
        )
        return

    floor_map = {f.floor_id: f for f in floors}
    rows = []
    for fa in scenario.floor_assignments:
        fid = f"{fa.tower_id}-F{fa.floor_number}"
        f = floor_map.get(fid)
        rows.append({
            "Unit": fa.unit_name,
            "Building": f.building_name if f else fa.building_id,
            "Tower": fa.tower_id,
            "Floor": fa.floor_number,
            "Floor ID": fid,
            "Seats Assigned": fa.seats_assigned,
            "Adjacency Tier": fa.adjacency_tier,
        })

    rows.sort(key=lambda r: (r["Unit"], r["Tower"], r["Floor"]))
    pd.DataFrame(rows).to_excel(writer, sheet_name="Floor Assignments", index=False)


def _write_risks_alerts(writer, scenario: Scenario, units: List[Unit],
                         attendance_map: Dict[str, AttendanceProfile], config: dict):
    if not scenario.allocation_results:
        pd.DataFrame([{"Note": "No results — run simulation first."}]).to_excel(
            writer, sheet_name="Risks & Alerts", index=False
        )
        return

    rto_alerts = compute_rto_alerts(scenario.allocation_results, units, attendance_map, config)
    rto_alert_map = {r["unit_name"]: r for r in rto_alerts}
    unit_map = {u.unit_name: u for u in units}

    rows = []

    # Capacity alerts
    for a in scenario.allocation_results:
        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
        risk = _risk_level(gap_pct, a.fragmentation_score)
        if risk in ("RED", "AMBER"):
            reasons = []
            if gap_pct < RISK_AMBER_GAP_PCT:
                reasons.append(f"Seat shortfall: {a.seat_gap:+d} seats ({gap_pct:.0%} of demand)")
            if a.fragmentation_score > 0.5:
                reasons.append(f"High fragmentation: {a.fragmentation_score:.2f}")
            rows.append({
                "Category": "Capacity",
                "Risk Level": risk,
                "Unit / Floor": a.unit_name,
                "Alert": "; ".join(reasons),
            })

    # RTO alerts
    for unit_name, ra in rto_alert_map.items():
        if ra["status"] in ("Under-utilized", "Under-allocated"):
            rows.append({
                "Category": "RTO",
                "Risk Level": "AMBER" if ra["status"] == "Under-utilized" else "RED",
                "Unit / Floor": unit_name,
                "Alert": f"{ra['status']}: Allocated {ra['allocated_seats']} seats, RTO Need {ra['expected_seats']} seats",
            })

    # RTO compliance alerts
    if scenario.params.global_rto_mandate_days:
        compliance = compute_rto_compliance(attendance_map, scenario.params.global_rto_mandate_days)
        for rc in compliance:
            if not rc["compliant"]:
                rows.append({
                    "Category": "RTO Compliance",
                    "Risk Level": "AMBER",
                    "Unit / Floor": rc["unit_name"],
                    "Alert": f"Below RTO mandate: {rc['actual_rto']:.1f} days/week vs target {rc['target_rto']:.1f}",
                })

    if not rows:
        rows.append({"Category": "—", "Risk Level": "GREEN", "Unit / Floor": "All units", "Alert": "No issues detected."})

    pd.DataFrame(rows).to_excel(writer, sheet_name="Risks & Alerts", index=False)


def _write_optimization_run(writer, run: dict):
    result = run.get("result")
    rows = []

    rows.append({"Field": "Timestamp", "Value": run.get("timestamp", "—")})
    rows.append({"Field": "Objective", "Value": run.get("objective", "—")})
    rows.append({"Field": "Status", "Value": run.get("status", "—")})
    rows.append({"Field": "Total Seats (Optimized)", "Value": run.get("total_seats", "—")})
    rows.append({"Field": "Floors Used", "Value": run.get("floors_used", "—")})

    if result and result.savings_summary:
        sv = result.savings_summary
        rows.append({"Field": "", "Value": ""})
        rows.append({"Field": "Allocation Rule Seats", "Value": sv.get("allocation_rule_seats", "—")})
        rows.append({"Field": "RTO-Based Seats", "Value": sv.get("rto_based_seats", "—")})
        rows.append({"Field": "Seats Saved", "Value": sv.get("seats_saved", "—")})
        rows.append({"Field": "Floors Freed", "Value": sv.get("floors_freed", "—")})

    summary_df = pd.DataFrame(rows)
    summary_df.to_excel(writer, sheet_name="Optimization Run", index=False)

    # Before/After per unit
    if result and result.before_after:
        ba_df = pd.DataFrame(result.before_after)
        ba_df.to_excel(writer, sheet_name="Optimization Run", index=False, startrow=len(rows) + 3)


def _write_demand_forecast(writer, daily_df):
    """Sheet: per-unit demand forecast summary from daily attendance data."""
    try:
        from engine.forecasting import compute_forecast_summary
        import numpy as np

        unit_names = sorted(daily_df["unit_name"].unique())
        summaries = compute_forecast_summary(daily_df, unit_names, forecast_months=6)

        if not summaries:
            pd.DataFrame([{"Note": "Insufficient daily data for forecasting (need ≥7 days per unit)."}]).to_excel(
                writer, sheet_name="Demand Forecast", index=False
            )
            return

        rows = []
        for s in summaries:
            # Also get trend slope
            from engine.forecasting import compute_unit_trend
            trend = compute_unit_trend(daily_df, s["unit_name"], forecast_months=6)
            rows.append({
                "Unit": s["unit_name"],
                "Current Median": s["current_median"],
                "Current Peak": s["current_peak"],
                "Forecasted Median (6m)": s["forecasted_median"],
                "Forecasted Peak (6m)": s["forecasted_peak"],
                "Suggested Annual Growth %": f"{s['suggested_growth_pct']:.1%}",
                "Trend Slope (seats/day)": f"{trend['trend_slope']:+.3f}" if trend else "—",
            })

        pd.DataFrame(rows).to_excel(writer, sheet_name="Demand Forecast", index=False)
    except Exception:
        pd.DataFrame([{"Note": "Demand forecast data unavailable."}]).to_excel(
            writer, sheet_name="Demand Forecast", index=False
        )


def _write_scenario_comparison(writer, matrix_results: list):
    """Sheet: ranked scenario comparison matrix results."""
    _PRIVATE_KEYS = {"_assignments", "_unit_allocations", "_temp_scenario", "_rc"}

    obj_labels = {
        "optimal_placement": "Optimal Placement",
        "rto_based": "RTO-Based",
        "rto_whatif": "What-If RTO",
    }

    rows = []
    for r in matrix_results:
        rows.append({
            "Rank": r.get("rank", "—"),
            "Alloc %": f"{r['alloc_pct']:.0%}" if r.get("alloc_pct") is not None else "N/A",
            "RTO (days/wk)": r.get("rto_mandate", "—"),
            "Capacity Reduction": f"{r.get('cap_red', 0):.0%}",
            "Mode": obj_labels.get(r.get("objective", ""), r.get("objective", "—")),
            "Demand (seats)": r.get("demand", "—"),
            "Capacity (seats)": r.get("capacity", "—"),
            "Headroom": r.get("headroom", "—"),
            "Total Gap": r.get("total_gap", "—"),
            "Units at Risk": r.get("units_at_risk", "—"),
            "Optimized Seats": r.get("opt_seats", "—"),
            "Floors Used": r.get("floors_used", "—"),
            "Avg Fragmentation": r.get("avg_fragmentation", "—"),
            "Seats Saved": r.get("seats_saved", "—"),
            "Optimizer Status": r.get("opt_status", "—"),
            "Composite Score": f"{r.get('composite_score', 0):.3f}",
        })

    if rows:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Scenario Comparison", index=False)
    else:
        pd.DataFrame([{"Note": "No scenario comparison results available."}]).to_excel(
            writer, sheet_name="Scenario Comparison", index=False
        )
