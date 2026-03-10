"""Holistic CPG Executive Report — PDF.

Produces a professional 7-page PDF covering all domains:
cover / strategic brief / scenario results / short-term risk /
floor intelligence / demand patterns / unit risk register.

Returns bytes for st.download_button.
"""

import io
from datetime import datetime
from typing import Optional, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, ListFlowable, ListItem,
)

from config.defaults import (
    RISK_RED_GAP_PCT, RISK_RED_FRAGMENTATION,
    RISK_AMBER_GAP_PCT, RISK_AMBER_FRAGMENTATION,
)

# ── Palette ────────────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1E3A5F")
NAVY_LITE  = colors.HexColor("#2E5090")
TEAL       = colors.HexColor("#17A589")
RED_BG     = colors.HexColor("#FFCCCC")
AMBER_BG   = colors.HexColor("#FFF3CC")
GREEN_BG   = colors.HexColor("#D5F5E3")
BLUE_BG    = colors.HexColor("#EBF5FF")
GREY_ROW   = colors.HexColor("#F5F5F5")
WHITE      = colors.white
BLACK      = colors.black
DARK_GREY  = colors.HexColor("#333333")
MID_GREY   = colors.HexColor("#666666")


# ── Styles ─────────────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("rh1", parent=base["Heading1"],
                         textColor=WHITE, fontSize=16, leading=22, spaceAfter=4)
    h2 = ParagraphStyle("rh2", parent=base["Heading2"],
                         textColor=NAVY, fontSize=13, leading=16,
                         spaceAfter=6, spaceBefore=10)
    h3 = ParagraphStyle("rh3", parent=base["Heading3"],
                         textColor=NAVY_LITE, fontSize=11, leading=14,
                         spaceAfter=4, spaceBefore=6)
    body = ParagraphStyle("rbody", parent=base["Normal"],
                           fontSize=9, leading=13, textColor=DARK_GREY)
    caption = ParagraphStyle("rcap", parent=base["Normal"],
                               fontSize=8, leading=11, textColor=MID_GREY,
                               fontName="Helvetica-Oblique")
    bold_body = ParagraphStyle("rboldb", parent=base["Normal"],
                                fontSize=9, leading=13, fontName="Helvetica-Bold")
    kpi_val = ParagraphStyle("rkpiv", parent=base["Normal"],
                              fontSize=22, leading=26, fontName="Helvetica-Bold",
                              textColor=NAVY, alignment=1)
    kpi_lbl = ParagraphStyle("rkpil", parent=base["Normal"],
                              fontSize=8, leading=10, alignment=1,
                              textColor=MID_GREY)
    cover_title = ParagraphStyle("rcovt", parent=base["Heading1"],
                                  textColor=WHITE, fontSize=22, leading=28,
                                  fontName="Helvetica-Bold", alignment=1, spaceAfter=6)
    cover_sub = ParagraphStyle("rcovs", parent=base["Normal"],
                                textColor=WHITE, fontSize=11, leading=15,
                                alignment=1)
    return h1, h2, h3, body, caption, bold_body, kpi_val, kpi_lbl, cover_title, cover_sub


# ── Shared building blocks ─────────────────────────────────────────────────────

def _risk_level(gap_pct: float, frag: float) -> str:
    if gap_pct < RISK_RED_GAP_PCT or frag > RISK_RED_FRAGMENTATION:
        return "RED"
    if gap_pct < RISK_AMBER_GAP_PCT or frag > RISK_AMBER_FRAGMENTATION:
        return "AMBER"
    return "GREEN"


def _risk_bg(level: str):
    return {"RED": RED_BG, "AMBER": AMBER_BG, "GREEN": GREEN_BG}.get(level, WHITE)


def _breach_tier(prob: float) -> str:
    if prob >= 0.20:
        return "HIGH"
    if prob >= 0.10:
        return "MEDIUM"
    return "LOW"


def _section_header(text, styles):
    _, h2, *_ = styles
    return [
        Spacer(1, 0.3 * cm),
        Paragraph(text, h2),
        HRFlowable(width="100%", thickness=1, color=NAVY_LITE,
                   spaceAfter=4, spaceBefore=0),
    ]


def _subsection_header(text, styles):
    _, _, h3, *_ = styles
    return [Spacer(1, 0.15 * cm), Paragraph(text, h3)]


def _std_table(header_row, data_rows, col_widths, row_bg_fn=None):
    all_rows = [header_row] + data_rows
    t = Table(all_rows, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
    ]
    for i, row in enumerate(data_rows, start=1):
        bg = row_bg_fn(i - 1, row) if row_bg_fn else (GREY_ROW if i % 2 == 0 else WHITE)
        cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(cmds))
    return t


def _kpi_strip(cells, styles):
    """4-cell KPI strip. cells = list of (value_str, label_str, [color])."""
    _, _, _, _, _, _, kpi_val, kpi_lbl, *_ = styles
    data = []
    for val_str, lbl_str, *rest in cells:
        col = rest[0] if rest else NAVY
        val_style = ParagraphStyle("kv", parent=kpi_val, textColor=col)
        data.append([Paragraph(val_str, val_style), Paragraph(lbl_str, kpi_lbl)])
    t = Table([data], colWidths=[f"{100//len(cells)}%" for _ in cells])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F4FA")),
        ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("INNERGRID",  (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MID_GREY)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    canvas.drawString(1.5 * cm, 0.8 * cm,
                      f"CPG Seat Planning Platform  |  {ts}  |  CONFIDENTIAL")
    canvas.drawRightString(A4[0] - 1.5 * cm, 0.8 * cm, f"Page {doc.page}")
    canvas.restoreState()


# ── Page builders ──────────────────────────────────────────────────────────────

def _page_cover(story, scenario, floors, units, styles):
    h1, h2, h3, body, caption, bold_body, kpi_val, kpi_lbl, cover_title, cover_sub = styles

    supply = sum(f.total_seats for f in floors) if floors else 0
    allocs = scenario.allocation_results or []
    demand = sum(a.effective_demand_seats for a in allocs)
    gap = supply - demand
    at_risk = sum(1 for a in allocs if a.seat_gap < 0)
    report_date = datetime.now().strftime("%B %d, %Y")

    # Full-width title block
    cover_table_data = [[
        Paragraph("CPG Workforce<br/>Seat Intelligence Report", cover_title),
    ]]
    cover_t = Table(cover_table_data, colWidths=["100%"])
    cover_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 30),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 30),
    ]))
    story.append(cover_t)
    story.append(Spacer(1, 0.4 * cm))

    # Scenario + date sub-header
    meta_data = [[Paragraph(
        f"<b>{scenario.name}</b>  ·  {scenario.scenario_type.capitalize()}  ·  {report_date}",
        cover_sub,
    )]]
    meta_t = Table(meta_data, colWidths=["100%"])
    meta_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY_LITE),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 0.8 * cm))

    # KPI strip
    gap_color = colors.HexColor("#006400") if gap >= 0 else colors.HexColor("#8B0000")
    story.append(_kpi_strip([
        (f"{supply:,}", "Seat Supply"),
        (f"{demand:,}", "Projected Demand"),
        (f"{gap:+,}", "Supply Headroom", gap_color),
        (str(at_risk), "Units at Risk"),
    ], styles))
    story.append(Spacer(1, 0.8 * cm))

    # About
    story.append(Paragraph("About This Report", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY_LITE,
                             spaceAfter=6, spaceBefore=0))
    story.append(Paragraph(
        "This report is generated by the <b>CPG Seat Planning & Scenario Intelligence Platform</b>. "
        "It provides CPG leadership with a unified view of workforce seat planning across all dimensions: "
        "policy-based scenario analysis, short-term demand forecasting, floor space intelligence, "
        "and unit-level risk assessment.",
        body,
    ))
    story.append(Spacer(1, 0.4 * cm))

    # Page guide
    story.append(Paragraph("Document Guide", h3))
    pages = [
        ("Page 1", "Cover — Scenario context, KPIs, document overview"),
        ("Page 2", "Strategic Brief — Key findings, recommended actions, CPG guidance"),
        ("Page 3", "Scenario & Capacity Results — Per-unit allocation, demand vs. supply, risk level"),
        ("Page 4", "Short-Term Demand & Risk — 10-day forecast, breach probability, overflow options"),
        ("Page 5", "Floor & Space Intelligence — Floor utilisation, consolidation opportunities"),
        ("Page 6", "Demand Patterns & Load Management — DOW patterns, clusters, stagger advisory"),
        ("Page 7", "Unit Risk Register — All units with every risk dimension on one page"),
    ]
    page_data = [[Paragraph(p, bold_body), Paragraph(d, body)] for p, d in pages]
    page_t = Table(page_data, colWidths=["22%", "78%"])
    page_t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
        *[("BACKGROUND",  (0, i), (-1, i), GREY_ROW if i % 2 == 1 else WHITE)
          for i in range(len(pages))],
    ]))
    story.append(page_t)
    story.append(PageBreak())


def _page_strategic_brief(story, scenario, floors, units, breach_data,
                           alert_days, conflict, clusters, stf_results,
                           matrix_results, has_daily, styles):
    h1, h2, h3, body, caption, bold_body, *_ = styles

    allocs = scenario.allocation_results or []
    supply = sum(f.total_seats for f in floors) if floors else 0
    demand = sum(a.effective_demand_seats for a in allocs)
    gap = supply - demand
    at_risk = sum(1 for a in allocs if a.seat_gap < 0)
    red_n = sum(1 for a in allocs if _risk_level(
        a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0,
        a.fragmentation_score) == "RED")
    overloaded_days = (conflict or {}).get("overloaded_days", [])
    high_breach = [d["unit_name"] for d in (breach_data or []) if d.get("breach_probability", 0) >= 0.20]
    risk_days = len(alert_days) if alert_days else 0

    story += _section_header("Strategic Brief", styles)
    story.append(Paragraph(
        f"This analysis covers <b>{len(units)}</b> business units across "
        f"<b>{len(set(f.building_id for f in floors)) if floors else '—'} building(s)</b> "
        f"under the <b>{scenario.name}</b> scenario "
        f"({scenario.scenario_type}, {scenario.planning_horizon_months}-month horizon). "
        f"Total physical seat supply is <b>{supply:,}</b> against projected demand of "
        f"<b>{demand:,}</b>, yielding a net "
        f"{'surplus' if gap >= 0 else 'shortfall'} of <b>{abs(gap):,} seats</b>. "
        + (f"<b>{at_risk} unit(s)</b> are individually at risk of capacity shortfall. " if at_risk else "")
        + (f"<b>{red_n} unit(s)</b> are at critical (RED) risk." if red_n else "All units meet minimum capacity thresholds."),
        body,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Key Findings
    story += _subsection_header("Key Findings", styles)
    findings = []
    if red_n > 0:
        worst = sorted(allocs, key=lambda a: a.seat_gap)[:2]
        findings.append(f"<b>{red_n} unit(s) at critical capacity risk</b> — {', '.join(a.unit_name for a in worst)} require immediate seat additions.")
    if gap > 200:
        findings.append(f"<b>Significant seat surplus of {gap:,}</b> — review if over-provisioned units can be right-sized or floors repurposed.")
    if has_daily and risk_days > 0:
        findings.append(f"<b>{risk_days} day(s) forecast above 90% capacity</b> in the next 10 days — overflow floor pre-positioning recommended.")
    if has_daily and overloaded_days:
        findings.append(f"<b>Persistent overload on {', '.join(overloaded_days)}</b> — stagger scheduling can reduce peak-day pressure.")
    if has_daily and high_breach:
        findings.append(f"<b>{len(high_breach)} unit(s) historically overflow ≥20% of days</b> ({', '.join(high_breach[:3])}) — allocation may need adjustment.")
    if not findings:
        findings.append("Capacity and demand are well-balanced across all units. Continue monitoring weekly.")

    story.append(ListFlowable(
        [ListItem(Paragraph(f, body), leftIndent=15, bulletColor=NAVY) for f in findings],
        bulletType="bullet",
        bulletFontSize=9,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Recommended Actions
    story += _subsection_header("Recommended Actions", styles)
    actions = []
    if red_n > 0:
        worst_unit = sorted(allocs, key=lambda a: a.seat_gap)[0]
        actions.append(f"<b>Immediate:</b> Allocate additional seats for <b>{worst_unit.unit_name}</b> (gap: {worst_unit.seat_gap:+,} seats).")
    if has_daily and risk_days > 0:
        actions.append(f"<b>This week:</b> Pre-designate overflow floors for the {risk_days} high-demand day(s). See Floor Intelligence page.")
    if has_daily and overloaded_days:
        actions.append(f"<b>Scheduling:</b> Work with unit managers to shift meetings/collaboration days away from {', '.join(overloaded_days)}.")
    if has_daily and high_breach:
        actions.append(f"<b>Policy review:</b> Increase allocation % for {', '.join(high_breach[:2])} to reduce historical overflow.")
    if matrix_results:
        best = next((r for r in matrix_results if r.get("rank") == 1), None)
        if best:
            actions.append(f"<b>Scenario:</b> Consider adopting Rank #1 scenario (RTO {best.get('rto_mandate')}d, {best.get('objective','')}) for better balance.")
    if not actions:
        actions.append("Continue with current scenario. Review forecasts monthly and re-run simulation if headcount changes exceed 5%.")

    story.append(ListFlowable(
        [ListItem(Paragraph(a, body), leftIndent=15, bulletColor=TEAL) for a in actions],
        bulletType="bullet",
        bulletFontSize=9,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # CPG guidance note
    story += _subsection_header("How CPG Can Use This Analysis", styles)
    story.append(Table([
        [Paragraph("<b>Annual seat planning</b>", bold_body),
         Paragraph("Validate allocation against projected HC growth under different RTO assumptions", body)],
        [Paragraph("<b>Capacity risk management</b>", bold_body),
         Paragraph("Identify units at overflow risk before it happens using short-term demand forecasts", body)],
        [Paragraph("<b>Floor consolidation</b>", bold_body),
         Paragraph("Spot under-utilised floors for sublease, renovation, or hot-desk conversion", body)],
        [Paragraph("<b>RTO policy assessment</b>", bold_body),
         Paragraph("Compare attendance-based vs mandate-driven demand to right-size provisioning", body)],
        [Paragraph("<b>Peak day operations</b>", bold_body),
         Paragraph("Pre-position overflow floors and stagger schedules on forecast-heavy days", body)],
    ], colWidths=["30%", "70%"],
    style=TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
        *[("BACKGROUND", (0, i), (-1, i), GREY_ROW if i % 2 == 0 else WHITE)
          for i in range(5)],
    ])))

    story.append(PageBreak())


def _page_scenario_results(story, scenario, units, attendance_map, rule_config, styles):
    from engine.allocation_engine import compute_rto_alerts
    h1, h2, h3, body, caption, bold_body, kpi_val, kpi_lbl, *_ = styles

    allocs = scenario.allocation_results or []
    story += _section_header("Scenario & Capacity Results", styles)

    if not allocs:
        story.append(Paragraph("No simulation results. Run Policy Simulation in What-If Analysis.", body))
        story.append(PageBreak())
        return

    demand = sum(a.effective_demand_seats for a in allocs)
    allocated = sum(a.allocated_seats for a in allocs)
    at_risk = sum(1 for a in allocs if a.seat_gap < 0)

    # Scenario context table
    ctx_data = [
        [Paragraph("<b>Scenario</b>", bold_body), Paragraph(scenario.name, body),
         Paragraph("<b>Type</b>", bold_body), Paragraph(scenario.scenario_type, body)],
        [Paragraph("<b>RTO Mandate</b>", bold_body),
         Paragraph(f"{scenario.params.global_rto_mandate_days}d/wk" if scenario.params.global_rto_mandate_days else "None", body),
         Paragraph("<b>Total Demand</b>", bold_body), Paragraph(f"{demand:,} seats", body)],
        [Paragraph("<b>Allocated</b>", bold_body), Paragraph(f"{allocated:,} seats", body),
         Paragraph("<b>Units at Risk</b>", bold_body), Paragraph(str(at_risk), body)],
    ]
    ctx_t = Table(ctx_data, colWidths=["20%", "30%", "20%", "30%"])
    ctx_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE_BG),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(ctx_t)
    story.append(Spacer(1, 0.3 * cm))

    # Per-unit allocation table
    rto_alerts = compute_rto_alerts(allocs, units, attendance_map, rule_config)
    rto_map = {r["unit_name"]: r for r in rto_alerts}
    unit_map = {u.unit_name: u for u in units}

    header = ["Unit", "Priority", "Demand", "Allocated", "Gap", "Risk", "RTO Status", "Alloc %"]
    rows = []
    for a in sorted(allocs, key=lambda x: x.seat_gap):
        u = unit_map.get(a.unit_name)
        ra = rto_map.get(a.unit_name)
        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
        risk = _risk_level(gap_pct, a.fragmentation_score)
        rows.append([
            a.unit_name,
            (u.business_priority or "—") if u else "—",
            str(a.effective_demand_seats),
            str(a.allocated_seats),
            f"{a.seat_gap:+,}",
            risk,
            ra["status"] if ra else "N/A",
            f"{a.recommended_alloc_pct:.0%}",
        ])

    def _row_bg(i, row):
        risk = row[5]
        return _risk_bg(risk)

    story.append(_std_table(header, rows, ["22%", "10%", "9%", "10%", "8%", "9%", "18%", "9%"],
                             row_bg_fn=_row_bg))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        "Risk: 🔴 RED = critical shortfall or high fragmentation · "
        "🟡 AMBER = approaching limit · 🟢 GREEN = healthy",
        caption,
    ))
    story.append(PageBreak())


def _page_stf_risk(story, scenario, stf_results, alert_days, breach_data, has_daily, styles):
    h1, h2, h3, body, caption, bold_body, *_ = styles
    story += _section_header("Short-Term Demand & Risk", styles)

    if not has_daily:
        story.append(Paragraph(
            "Short-term demand data not available. Load daily attendance history "
            "in the Admin tab to enable this section.", body))
        story.append(PageBreak())
        return

    allocs = scenario.allocation_results or []
    supply_total = sum(a.allocated_seats for a in allocs)
    risk_days = len(alert_days) if alert_days else 0

    # Aggregate per-unit per-day stf_results to daily totals
    from config.defaults import FORECAST_CAPACITY_ALERT_THRESHOLD
    daily_agg: dict = {}
    for r in (stf_results or []):
        date_key = str(r.get("date", ""))[:10]
        if date_key not in daily_agg:
            daily_agg[date_key] = {"weekday_name": r.get("weekday_name", ""), "expected_seats": 0}
        daily_agg[date_key]["expected_seats"] += r.get("expected_seats", 0)

    n_days = len(daily_agg)
    alert_day_count = sum(
        1 for v in daily_agg.values()
        if supply_total > 0 and v["expected_seats"] / supply_total > FORECAST_CAPACITY_ALERT_THRESHOLD
    )

    story.append(Paragraph(
        f"The next <b>{n_days} business days</b> "
        f"are forecast below. <b>{alert_day_count} day(s)</b> exceed 90% of total allocated capacity "
        f"({supply_total:,} seats).",
        body,
    ))
    story.append(Spacer(1, 0.2 * cm))

    # STF table (compact — max 15 rows, one row per day)
    if daily_agg:
        stf_header = ["Date", "Day", "Expected Seats", "Capacity %", "Alert"]
        stf_rows = []
        for date_key in sorted(daily_agg):
            expected = daily_agg[date_key]["expected_seats"]
            cap_pct = expected / supply_total if supply_total > 0 else 0
            stf_rows.append([
                date_key,
                daily_agg[date_key]["weekday_name"],
                str(expected),
                f"{cap_pct:.0%}",
                "⚠ Over 90%" if cap_pct > FORECAST_CAPACITY_ALERT_THRESHOLD else "",
            ])

        def _stf_bg(i, row):
            return AMBER_BG if row[4] else (GREY_ROW if i % 2 == 0 else WHITE)

        story.append(_std_table(stf_header, stf_rows,
                                 ["18%", "16%", "18%", "16%", "32%"],
                                 row_bg_fn=_stf_bg))
        story.append(Spacer(1, 0.3 * cm))

    # Breach risk table
    if breach_data:
        story += _subsection_header("Historical Capacity Breach Risk by Unit", styles)
        story.append(Paragraph(
            "Based on historical attendance: probability that daily occupancy exceeds allocated seats.",
            caption,
        ))
        story.append(Spacer(1, 0.1 * cm))
        br_header = ["Unit", "Risk Tier", "% Days Overflow", "Overflow Days/Month", "Seats to Add"]
        import math
        br_rows = []
        for d in sorted(breach_data, key=lambda x: -x.get("breach_probability", 0)):
            prob = d.get("breach_probability", 0)
            tier = _breach_tier(prob)
            mag = d.get("avg_breach_magnitude", 0)
            seats_add = int(math.ceil(mag / 5) * 5) if mag > 0 else 0
            br_rows.append([
                d["unit_name"],
                tier,
                f"{prob:.0%}",
                f"~{d.get('expected_breach_days_per_month', 0):.0f}",
                f"+{seats_add}" if seats_add > 0 else "—",
            ])

        def _br_bg(i, row):
            tier = row[1]
            return {"HIGH": RED_BG, "MEDIUM": AMBER_BG, "LOW": GREEN_BG}.get(tier, WHITE)

        story.append(_std_table(br_header, br_rows,
                                 ["30%", "14%", "18%", "20%", "18%"],
                                 row_bg_fn=_br_bg))

    story.append(PageBreak())


def _page_floor_intelligence(story, scenario, floors, styles):
    from engine.spatial import get_floor_utilization
    h1, h2, h3, body, caption, *_ = styles
    story += _section_header("Floor & Space Intelligence", styles)

    floor_assignments = scenario.floor_assignments or []
    if not floors or not floor_assignments:
        story.append(Paragraph("No floor assignment data. Run Policy Simulation first.", body))
        story.append(PageBreak())
        return

    util = get_floor_utilization(floors, floor_assignments)
    supply_total = sum(f.total_seats for f in floors)
    occupied_total = sum(u.get("used_seats", 0) for u in util)

    story.append(Paragraph(
        f"<b>{len(floors)} floors</b> across "
        f"<b>{len(set(f.building_id for f in floors))} building(s)</b>. "
        f"Total supply: <b>{supply_total:,} seats</b>. "
        f"Currently occupied: <b>{occupied_total:,} seats</b> "
        f"({occupied_total / supply_total:.0%} utilisation).",
        body,
    ))
    story.append(Spacer(1, 0.2 * cm))

    fl_header = ["Tower", "Floor", "Total Seats", "Occupied", "Available", "Util %", "Status"]
    fl_rows = []
    for f in sorted(util, key=lambda x: (x.get("tower_id", ""), x.get("floor_number", 0))):
        total = f.get("total_seats", 0)
        occ = f.get("used_seats", 0)
        avail = f.get("available_seats", 0)
        up = f.get("utilization_pct", occ / total if total > 0 else 0)
        status = (
            "Near capacity" if up >= 0.90 else
            "Healthy" if up >= 0.60 else
            "Under-utilised" if up > 0 else "Empty"
        )
        fl_rows.append([
            f.get("tower_id", "—"),
            str(f.get("floor_number", "—")),
            str(total), str(occ), str(avail),
            f"{up:.0%}",
            status,
        ])

    def _fl_bg(i, row):
        status = row[6]
        if "Near" in status:
            return AMBER_BG
        if "Under" in status or "Empty" in status:
            return BLUE_BG
        return GREY_ROW if i % 2 == 0 else WHITE

    story.append(_std_table(fl_header, fl_rows,
                             ["18%", "10%", "14%", "12%", "12%", "12%", "22%"],
                             row_bg_fn=_fl_bg))

    # Consolidation opportunities: floors below 40% utilised
    low_util = [f for f in util if 0 < f.get("utilization_pct", 0) < 0.40]
    if low_util:
        story.append(Spacer(1, 0.3 * cm))
        story += _subsection_header("Consolidation Opportunities", styles)
        story.append(Paragraph(
            "These floors are below 40% utilised and may be candidates for consolidation, "
            "sublease, or hot-desk conversion.",
            caption,
        ))
        cs_header = ["Floor ID", "Tower", "Util %", "Available Seats", "Recommendation"]
        cs_rows = [[
            f.get("floor_id", "—"),
            f.get("tower_id", "—"),
            f"{f.get('utilization_pct', 0):.0%}",
            str(f.get("available_seats", "—")),
            "Consider sublease/decommission" if f.get("utilization_pct", 0) < 0.20 else "Candidate for flex/hot-desk",
        ] for f in sorted(low_util, key=lambda x: x.get("utilization_pct", 0))]
        story.append(_std_table(cs_header, cs_rows, ["20%", "14%", "12%", "18%", "36%"]))

    story.append(PageBreak())


def _page_demand_patterns(story, dow_df, clusters, conflict, peak_data, has_daily, styles):
    h1, h2, h3, body, caption, bold_body, *_ = styles
    story += _section_header("Demand Patterns & Load Management", styles)

    if not has_daily:
        story.append(Paragraph(
            "Load daily attendance history in the Admin tab to enable this section.", body))
        story.append(PageBreak())
        return

    # DOW pivot (compact)
    if dow_df is not None and not dow_df.empty:
        story += _subsection_header("Day-of-Week Attendance Patterns (Median Seats)", styles)
        story.append(Paragraph("◀ = peak attendance day for that unit", caption))
        story.append(Spacer(1, 0.1 * cm))
        try:
            import pandas as pd
            DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            pivot = dow_df.pivot_table(
                index="unit_name", columns="day_name",
                values="median_count", aggfunc="sum",
            ).reindex(columns=DAY_ORDER, fill_value=0)
            pivot.index.name = None
            pivot.columns.name = None

            header = ["Unit"] + DAY_ORDER
            rows = []
            for unit_name, row in pivot.iterrows():
                vals = [int(row[d]) for d in DAY_ORDER]
                peak_idx = vals.index(max(vals)) if vals else -1
                row_cells = [str(unit_name)]
                for i, v in enumerate(vals):
                    row_cells.append(f"{v} ◀" if i == peak_idx else str(v))
                rows.append(row_cells)

            def _dow_bg(i, row):
                return GREY_ROW if i % 2 == 0 else WHITE

            story.append(_std_table(header, rows,
                                     ["26%", "15%", "15%", "15%", "15%", "14%"],
                                     row_bg_fn=_dow_bg))
        except Exception:
            story.append(Paragraph("DOW pattern data could not be rendered.", caption))

        story.append(Spacer(1, 0.3 * cm))

    # Stagger suggestions
    overloaded = (conflict or {}).get("overloaded_days", [])
    suggestions = (conflict or {}).get("suggestions", [])
    if overloaded or suggestions:
        story += _subsection_header("Load Balancing Advisory", styles)
        if overloaded:
            story.append(Paragraph(
                f"<b>Overloaded days (consistently above capacity):</b> {', '.join(overloaded)}. "
                "Consider shifting meetings, workshops, or optional in-office days.",
                body,
            ))
            story.append(Spacer(1, 0.1 * cm))
        if suggestions:
            sg_header = ["Unit", "Current Peak DOW", "Suggested Stagger DOW", "Est. Reduction"]
            sg_rows = [[
                s.get("unit_name", "—"),
                s.get("current_peak_dow", "—"),
                s.get("suggested_dow", "—"),
                str(s.get("estimated_reduction", "—")),
            ] for s in suggestions]
            story.append(_std_table(sg_header, sg_rows, ["30%", "20%", "25%", "25%"]))
        story.append(Spacer(1, 0.2 * cm))

    # Cluster summary
    if clusters:
        story += _subsection_header("Attendance Cluster Groups", styles)
        story.append(Paragraph(
            "Units in the same group have correlated attendance patterns (r ≥ 0.7). "
            "Co-locating same-cluster units concentrates peak-day demand on the same floors.",
            caption,
        ))
        story.append(Spacer(1, 0.1 * cm))
        import collections
        cluster_peers: dict = collections.defaultdict(list)
        for c in clusters:
            cid = c.get("cluster_id")
            if cid is not None:
                cluster_peers[cid].append(c.get("unit_name", ""))

        cl_header = ["Cluster", "Units", "Co-Peak Risk"]
        cl_rows = []
        for cid, peers in sorted(cluster_peers.items()):
            cl_rows.append([
                f"Group {cid}",
                ", ".join(peers),
                "High — avoid same-floor placement" if len(peers) > 2 else
                "Medium — monitor" if len(peers) > 1 else "Low",
            ])

        def _cl_bg(i, row):
            risk = row[2]
            return RED_BG if "High" in risk else AMBER_BG if "Medium" in risk else GREEN_BG

        story.append(_std_table(cl_header, cl_rows, ["14%", "56%", "30%"],
                                 row_bg_fn=_cl_bg))

    story.append(PageBreak())


def _page_unit_risk_register(story, scenario, units, attendance_map, rule_config,
                              breach_data, stf_results, clusters, has_daily, styles):
    import math
    from engine.allocation_engine import compute_rto_alerts
    h1, h2, h3, body, caption, bold_body, *_ = styles

    allocs = scenario.allocation_results or []
    story += _section_header("Unit Risk Register", styles)
    story.append(Paragraph(
        "Comprehensive per-unit view combining all risk dimensions. "
        "Sort: highest risk first.",
        caption,
    ))
    story.append(Spacer(1, 0.2 * cm))

    if not allocs:
        story.append(Paragraph("No simulation results. Run Policy Simulation first.", body))
        return

    rto_alerts = compute_rto_alerts(allocs, units, attendance_map, rule_config)
    rto_map = {r["unit_name"]: r for r in rto_alerts}
    breach_map = {d["unit_name"]: d for d in (breach_data or [])}
    cluster_map = {c["unit_name"]: c.get("cluster_id") for c in (clusters or [])}
    unit_map = {u.unit_name: u for u in units}

    stf_peak_map = {}
    if stf_results:
        for r in stf_results:
            name = r.get("unit_name")
            if name:
                stf_peak_map[name] = max(stf_peak_map.get(name, 0), r.get("expected_seats", 0))

    header = ["Unit", "Risk", "Gap", "RTO Status", "Breach Risk", "STF Peak", "Cluster", "Action"]
    rows = []
    for a in sorted(allocs, key=lambda x: x.seat_gap):
        ra = rto_map.get(a.unit_name)
        bd = breach_map.get(a.unit_name)
        cid = cluster_map.get(a.unit_name)
        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats > 0 else 0
        risk = _risk_level(gap_pct, a.fragmentation_score)
        breach_prob = bd.get("breach_probability", 0) if bd else None
        btier = _breach_tier(breach_prob) if breach_prob is not None else "N/A"
        stf_peak = str(stf_peak_map.get(a.unit_name, "N/A")) if has_daily else "N/A"

        if risk == "RED" and a.seat_gap < 0:
            action = f"Add {abs(a.seat_gap)} seats"
        elif risk == "AMBER" and a.seat_gap < 0:
            action = "Plan increase (3mo)"
        elif btier == "HIGH":
            action = "Adjust allocation"
        elif a.fragmentation_score > 0.6:
            action = "Consolidate floors"
        elif a.seat_gap > 30:
            action = "Consider right-sizing"
        else:
            action = "No action needed"

        rows.append([
            a.unit_name,
            risk,
            f"{a.seat_gap:+,}",
            ra["status"] if ra else "N/A",
            btier,
            stf_peak,
            f"Grp {cid}" if cid is not None else "—",
            action,
        ])

    def _reg_bg(i, row):
        return _risk_bg(row[1])

    story.append(_std_table(header, rows,
                             ["20%", "8%", "7%", "14%", "10%", "8%", "8%", "25%"],
                             row_bg_fn=_reg_bg))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Risk: RED = critical shortfall / high fragmentation · "
        "AMBER = approaching limit · GREEN = healthy.  "
        "Breach Risk: HIGH = overflows ≥20% of days historically.  "
        "STF Peak = max expected seats in next 10-day forecast window.",
        caption,
    ))


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_holistic_pdf_report(
    scenario,
    floors: list,
    units: list,
    att_map: dict,
    rule_config: dict,
    daily_df=None,
    unit_names: Optional[List[str]] = None,
    stf_results: Optional[list] = None,
    alert_days: Optional[list] = None,
    dow_df=None,
    conflict: Optional[dict] = None,
    peak_data: Optional[list] = None,
    breach_data: Optional[list] = None,
    clusters: Optional[list] = None,
    matrix_results: Optional[list] = None,
) -> bytes:
    """
    Generate a holistic 7-page executive PDF report.
    Returns bytes for st.download_button.
    """
    has_daily = daily_df is not None and not daily_df.empty
    output = io.BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
        title=f"CPG Executive Report — {scenario.name}",
        author="CPG Seat Planning Platform",
    )

    styles = _styles()
    story = []

    # Build attendance_map from att_map if it's already a dict
    attendance_map = att_map if isinstance(att_map, dict) else {a.unit_name: a for a in att_map}

    _page_cover(story, scenario, floors, units, styles)
    _page_strategic_brief(story, scenario, floors, units, breach_data,
                           alert_days, conflict, clusters, stf_results,
                           matrix_results, has_daily, styles)
    _page_scenario_results(story, scenario, units, attendance_map, rule_config, styles)
    _page_stf_risk(story, scenario, stf_results, alert_days, breach_data, has_daily, styles)
    _page_floor_intelligence(story, scenario, floors, styles)
    _page_demand_patterns(story, dow_df, clusters, conflict, peak_data, has_daily, styles)
    _page_unit_risk_register(story, scenario, units, attendance_map, rule_config,
                              breach_data, stf_results, clusters, has_daily, styles)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
