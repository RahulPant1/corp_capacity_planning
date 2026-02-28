"""PDF Boardroom Report generator — produces a professional multi-page PDF
using reportlab.platypus. No AI dependency. Returns bytes for st.download_button."""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)

from config.defaults import (
    RISK_RED_GAP_PCT, RISK_RED_FRAGMENTATION,
    RISK_AMBER_GAP_PCT, RISK_AMBER_FRAGMENTATION,
)

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1E3A5F")
NAVY_LIGHT = colors.HexColor("#2E5090")
RED_BG     = colors.HexColor("#FFCCCC")
AMBER_BG   = colors.HexColor("#FFF3CC")
GREEN_BG   = colors.HexColor("#CCFFCC")
GREY_ROW   = colors.HexColor("#F5F5F5")
WHITE      = colors.white
BLACK      = colors.black
DARK_GREY  = colors.HexColor("#333333")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _risk_level(gap_pct: float, frag: float) -> str:
    if gap_pct < RISK_RED_GAP_PCT or frag > RISK_RED_FRAGMENTATION:
        return "RED"
    if gap_pct < RISK_AMBER_GAP_PCT or frag > RISK_AMBER_FRAGMENTATION:
        return "AMBER"
    return "GREEN"


def _risk_bg(level: str):
    return {"RED": RED_BG, "AMBER": AMBER_BG, "GREEN": GREEN_BG}.get(level, WHITE)


def _styles():
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("rh1", parent=base["Heading1"],
                         textColor=WHITE, fontSize=16, leading=20,
                         spaceAfter=4)
    h2 = ParagraphStyle("rh2", parent=base["Heading2"],
                         textColor=NAVY, fontSize=13, leading=16,
                         spaceAfter=6, spaceBefore=10)
    body = ParagraphStyle("rbody", parent=base["Normal"],
                          fontSize=9, leading=13, textColor=DARK_GREY)
    caption = ParagraphStyle("rcaption", parent=base["Normal"],
                              fontSize=8, leading=11,
                              textColor=colors.HexColor("#666666"),
                              italics=True)
    bold = ParagraphStyle("rbold", parent=base["Normal"],
                          fontSize=9, leading=13, fontName="Helvetica-Bold")
    kpi_val = ParagraphStyle("rkpiv", parent=base["Normal"],
                              fontSize=20, leading=24, fontName="Helvetica-Bold",
                              textColor=NAVY, alignment=1)
    kpi_lbl = ParagraphStyle("rkpil", parent=base["Normal"],
                              fontSize=8, leading=10, alignment=1,
                              textColor=colors.HexColor("#555555"))
    return h1, h2, body, caption, bold, kpi_val, kpi_lbl


def _header_table(title: str, scenario_name: str, report_date: str, styles):
    h1, *_ = styles
    data = [[Paragraph(f"<b>{title}</b>", h1),
             Paragraph(f"<b>{scenario_name}</b><br/>{report_date}", h1)]]
    t = Table(data, colWidths=["60%", "40%"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR",  (0, 0), (-1, -1), WHITE),
        ("ALIGN",      (1, 0),  (1, 0), "RIGHT"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    return t


def _kpi_table(supply, demand, gap, at_risk, styles):
    _, _, _, _, _, kpi_val, kpi_lbl = styles
    gap_color = colors.HexColor("#006400") if gap >= 0 else colors.HexColor("#8B0000")
    kpi_val_gap = ParagraphStyle("rkpivg", parent=kpi_val._baseFontName and kpi_val or kpi_val,
                                  fontSize=20, leading=24, fontName="Helvetica-Bold",
                                  textColor=gap_color, alignment=1)

    def _cell(val_str, label, val_style=None):
        return [Paragraph(val_str, val_style or kpi_val),
                Paragraph(label, kpi_lbl)]

    data = [[
        _cell(f"{supply:,}", "Seat Supply"),
        _cell(f"{demand:,}", "Total Demand"),
        _cell(f"{gap:+,}", "Net Gap", kpi_val_gap),
        _cell(str(at_risk), "Units at Risk"),
    ]]
    t = Table(data, colWidths=["25%", "25%", "25%", "25%"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F4FA")),
        ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("INNERGRID",  (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _section_header(text, styles):
    _, h2, *_ = styles
    return [
        Spacer(1, 0.3 * cm),
        Paragraph(text, h2),
        HRFlowable(width="100%", thickness=1, color=NAVY_LIGHT,
                   spaceAfter=4, spaceBefore=0),
    ]


def _std_table(header_row, data_rows, col_widths, row_bg_fn=None):
    """Build a standard table with navy header and alternating / colored rows."""
    all_rows = [header_row] + data_rows
    t = Table(all_rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
    ]
    for i, row in enumerate(data_rows, start=1):
        bg = row_bg_fn(i - 1, row) if row_bg_fn else (GREY_ROW if i % 2 == 0 else WHITE)
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t


# ── Page footer ───────────────────────────────────────────────────────────────
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#888888"))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    canvas.drawString(1.5 * cm, 0.8 * cm,
                      f"Generated by CPG Seat Planning Platform | {ts} | CONFIDENTIAL")
    canvas.drawRightString(A4[0] - 1.5 * cm, 0.8 * cm,
                           f"Page {doc.page}")
    canvas.restoreState()


# ── Main entry point ──────────────────────────────────────────────────────────
def generate_pdf_report(scenario, floors, units, attendance_map,
                        rule_config, opt_history=None) -> bytes:
    """Generate a boardroom-ready PDF and return it as bytes."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.8 * cm,
    )
    styles = _styles()
    _, _, body, caption, bold, *_ = styles

    allocs = scenario.allocation_results
    assignments = scenario.floor_assignments
    report_date = datetime.now().strftime("%d %B %Y")
    story = []

    # ── PAGE 1: EXECUTIVE SUMMARY ─────────────────────────────────────────────
    story.append(_header_table("CPG Seat Planning Report",
                               scenario.name, report_date, styles))
    story.append(Spacer(1, 0.4 * cm))

    total_supply = sum(f.total_seats for f in floors)
    total_demand = sum(a.effective_demand_seats for a in allocs)
    total_alloc  = sum(a.allocated_seats for a in allocs)
    net_gap      = total_alloc - total_demand
    at_risk      = sum(1 for a in allocs if a.seat_gap < 0)

    story.append(_kpi_table(total_supply, total_demand, net_gap, at_risk, styles))
    story.append(Spacer(1, 0.4 * cm))

    # Scenario metadata
    last_run = (scenario.last_run_at.strftime("%d %b %Y, %H:%M")
                if scenario.last_run_at else "Not yet run")
    meta_rows = [
        ["Scenario Type",       scenario.scenario_type.capitalize()],
        ["Planning Horizon",    f"{scenario.planning_horizon_months} months"],
        ["Last Simulation Run", last_run],
        ["Global Alloc %",      f"{rule_config.get('global_alloc_pct', 0.80):.0%}"],
        ["Planning Buffer",     rule_config.get('planning_buffer_level', 'balanced').capitalize()],
    ]
    if scenario.params.excluded_floors:
        meta_rows.append(["Excluded Floors",
                           ", ".join(scenario.params.excluded_floors)])

    meta_t = Table([[Paragraph(r[0], bold), Paragraph(r[1], body)]
                    for r in meta_rows],
                   colWidths=["35%", "65%"])
    meta_t.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
        *[("BACKGROUND", (0, i), (-1, i), GREY_ROW if i % 2 else WHITE)
          for i in range(len(meta_rows))],
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 0.4 * cm))

    # Risk distribution summary
    red_n   = sum(1 for a in allocs
                  if _risk_level(a.seat_gap / a.effective_demand_seats
                                 if a.effective_demand_seats else 0,
                                 a.fragmentation_score) == "RED")
    amber_n = sum(1 for a in allocs
                  if _risk_level(a.seat_gap / a.effective_demand_seats
                                 if a.effective_demand_seats else 0,
                                 a.fragmentation_score) == "AMBER")
    green_n = len(allocs) - red_n - amber_n

    story.extend(_section_header("Risk Distribution", styles))
    risk_t = Table(
        [["🔴 RED", "🟡 AMBER", "🟢 GREEN", "Total Units"],
         [str(red_n), str(amber_n), str(green_n), str(len(allocs))]],
        colWidths=["25%", "25%", "25%", "25%"],
    )
    risk_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), RED_BG),
        ("BACKGROUND",    (1, 0), (1, 0), AMBER_BG),
        ("BACKGROUND",    (2, 0), (2, 0), GREEN_BG),
        ("BACKGROUND",    (3, 0), (3, 0), colors.HexColor("#E8E8E8")),
        ("BACKGROUND",    (0, 1), (0, 1), RED_BG),
        ("BACKGROUND",    (1, 1), (1, 1), AMBER_BG),
        ("BACKGROUND",    (2, 1), (2, 1), GREEN_BG),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ]))
    story.append(risk_t)

    # ── PAGE 2: ALLOCATION BY UNIT ────────────────────────────────────────────
    story.append(PageBreak())
    story.append(_header_table("CPG Seat Planning Report",
                               scenario.name, report_date, styles))
    story.extend(_section_header("Allocation by Unit", styles))
    story.append(Paragraph(
        "Color key: 🔴 RED = seat shortfall or high fragmentation  "
        "🟡 AMBER = moderate risk  🟢 GREEN = healthy allocation",
        caption))
    story.append(Spacer(1, 0.2 * cm))

    unit_map = {u.unit_name: u for u in units}
    alloc_header = ["Unit", "Priority", "Policy Demand", "Allocated", "Gap", "Alloc %", "Risk"]
    alloc_data = []
    alloc_levels = []
    for a in allocs:
        u = unit_map.get(a.unit_name)
        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0
        level = _risk_level(gap_pct, a.fragmentation_score)
        alloc_levels.append(level)
        alloc_data.append([
            a.unit_name,
            (u.business_priority or "—") if u else "—",
            str(a.effective_demand_seats),
            str(a.allocated_seats),
            f"{a.seat_gap:+d}",
            f"{a.recommended_alloc_pct:.1%}",
            level,
        ])

    def alloc_row_bg(i, _row):
        return _risk_bg(alloc_levels[i])

    story.append(_std_table(
        alloc_header, alloc_data,
        ["28%", "12%", "13%", "13%", "10%", "12%", "12%"],
        alloc_row_bg,
    ))

    # ── PAGE 3: FLOOR ASSIGNMENTS ─────────────────────────────────────────────
    if assignments:
        story.append(PageBreak())
        story.append(_header_table("CPG Seat Planning Report",
                                   scenario.name, report_date, styles))
        story.extend(_section_header("Floor Assignments", styles))

        fa_header = ["Unit", "Building", "Tower", "Floor", "Seats", "Adjacency"]
        fa_data = [
            [a.unit_name, a.building_id, a.tower_id,
             str(a.floor_number), str(a.seats_assigned), a.adjacency_tier]
            for a in sorted(assignments,
                            key=lambda x: (x.building_id, x.tower_id, x.floor_number))
        ]
        story.append(_std_table(
            fa_header, fa_data,
            ["28%", "14%", "14%", "10%", "12%", "22%"],
        ))

    # ── PAGE 4: RISKS & ALERTS ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(_header_table("CPG Seat Planning Report",
                               scenario.name, report_date, styles))
    story.extend(_section_header("Risks & Alerts", styles))

    risk_items = []
    for a in allocs:
        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0
        level = _risk_level(gap_pct, a.fragmentation_score)
        if level in ("RED", "AMBER"):
            reasons = []
            if gap_pct < RISK_AMBER_GAP_PCT:
                reasons.append(f"seat shortfall {gap_pct:.0%} of demand ({a.seat_gap:+d} seats)")
            if a.fragmentation_score > RISK_AMBER_FRAGMENTATION:
                reasons.append(f"high fragmentation (score {a.fragmentation_score:.2f})")
            risk_items.append((level, a.unit_name, " | ".join(reasons)))

    if risk_items:
        risk_header = ["Level", "Unit", "Reason"]
        risk_rows   = [[lvl, nm, rsn] for lvl, nm, rsn in risk_items]

        def risk_row_bg(i, _row):
            return _risk_bg(risk_items[i][0])

        story.append(_std_table(risk_header, risk_rows,
                                ["12%", "25%", "63%"], risk_row_bg))
    else:
        story.append(Paragraph("No RED or AMBER units — all allocations are healthy.", body))

    # ── PAGE 5 (conditional): OPTIMIZATION RESULTS ───────────────────────────
    opt_run = opt_history[-1] if opt_history else None
    if opt_run:
        story.append(PageBreak())
        story.append(_header_table("CPG Seat Planning Report",
                                   scenario.name, report_date, styles))
        story.extend(_section_header("Optimization Results", styles))

        opt_meta = [
            ["Objective",       opt_run.get("objective", "—")],
            ["Status",          opt_run.get("status", "—")],
            ["Run At",          opt_run.get("timestamp", "—")],
            ["Seats Saved",     str(opt_run.get("seats_saved", "—"))],
            ["Floors Freed",    str(opt_run.get("floors_freed", "—"))],
            ["Policy-Based Seats", str(opt_run.get("alloc_rule_seats", "—"))],
            ["Attendance-Based Seats", str(opt_run.get("rto_based_seats", "—"))],
        ]
        opt_t = Table([[Paragraph(r[0], bold), Paragraph(str(r[1]), body)]
                       for r in opt_meta],
                      colWidths=["40%", "60%"])
        opt_t.setStyle(TableStyle([
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            *[("BACKGROUND", (0, i), (-1, i), GREY_ROW if i % 2 else WHITE)
              for i in range(len(opt_meta))],
        ]))
        story.append(opt_t)

        # Before/after per-unit comparison
        if "unit_results" in opt_run:
            story.append(Spacer(1, 0.4 * cm))
            story.extend(_section_header("Before / After by Unit", styles))
            ba_header = ["Unit", "Before (seats)", "After (seats)", "Change"]
            ba_data = []
            for unit_name, after_seats in opt_run["unit_results"].items():
                before = next((a.effective_demand_seats for a in allocs
                               if a.unit_name == unit_name), after_seats)
                change = after_seats - before
                ba_data.append([unit_name, str(before), str(after_seats), f"{change:+d}"])
            story.append(_std_table(ba_header, ba_data,
                                    ["40%", "20%", "20%", "20%"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
