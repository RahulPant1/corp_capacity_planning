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
    kpi_val_gap = ParagraphStyle("rkpivg", parent=kpi_val,
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


def _executive_summary_text(scenario, floors, allocs, opt_history=None):
    """Generate a rule-based executive brief paragraph from scenario data."""
    n_buildings = len(set(f.building_id for f in floors))
    supply = sum(f.total_seats for f in floors)
    demand = sum(a.effective_demand_seats for a in allocs)
    alloc = sum(a.allocated_seats for a in allocs)
    gap = alloc - demand
    gap_word = "surplus" if gap >= 0 else "shortfall"
    at_risk = sum(1 for a in allocs if a.seat_gap < 0)
    n_units = len(allocs)

    lines = [
        f"This report presents the seat planning analysis for scenario "
        f"\"{scenario.name}\" ({scenario.scenario_type}) over a "
        f"{scenario.planning_horizon_months}-month planning horizon.",
        "",
        f"Total seat supply across {n_buildings} building(s) is {supply:,} seats "
        f"against a projected demand of {demand:,} seats, resulting in a net "
        f"{gap_word} of {abs(gap):,} seats. "
        f"{at_risk} of {n_units} business unit(s) are flagged as at-risk due to "
        f"seat shortfalls or high fragmentation.",
    ]

    # Hot-seating savings
    hot_savings = sum(a.hot_seat_savings for a in allocs)
    if hot_savings > 0:
        shift_units = sum(1 for a in allocs if a.hot_seat_savings > 0)
        physical = sum(a.physical_demand for a in allocs)
        lines.append("")
        lines.append(
            f"Hot-seating across {shift_units} unit(s) with night shifts saves "
            f"{hot_savings:,} seats, reducing physical demand to {physical:,}."
        )

    # Risk sentence
    red_n = sum(1 for a in allocs
                if (a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0)
                < -0.15 or a.fragmentation_score > 0.7)
    amber_n = sum(1 for a in allocs
                  if (a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0)
                  < -0.05 or a.fragmentation_score > 0.5) - red_n
    lines.append("")
    if red_n > 0 or amber_n > 0:
        worst = sorted(allocs, key=lambda a: a.seat_gap)[:2]
        names = ", ".join(a.unit_name for a in worst)
        lines.append(
            f"{red_n} unit(s) are RED risk (critical shortfall), {amber_n} are AMBER. "
            f"Key concerns: {names}."
        )
    else:
        lines.append("All units are GREEN — no critical risks identified.")

    # Recommendation
    lines.append("")
    opt_run = opt_history[-1] if opt_history else None
    if opt_run:
        saved = opt_run.get("seats_saved", 0)
        freed = opt_run.get("floors_freed", 0)
        lines.append(
            f"Optimization has been applied — {saved} seats saved, "
            f"{freed} floor(s) freed."
        )
    else:
        lines.append(
            "Consider running LP optimization to consolidate placements "
            "and recover underutilized seats."
        )

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────
def generate_pdf_report(scenario, floors, units, attendance_map,
                        rule_config, opt_history=None,
                        daily_attendance_df=None,
                        matrix_results=None) -> bytes:
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

    # Executive Summary brief
    exec_summary = _executive_summary_text(scenario, floors, allocs, opt_history)
    exec_style = ParagraphStyle(
        "exec_brief", parent=body,
        fontSize=9, leading=13, backColor=colors.HexColor("#EBF5FF"),
        borderPadding=8, spaceBefore=4, spaceAfter=8,
    )
    story.extend(_section_header("Executive Summary", styles))
    for para_text in exec_summary.split("\n\n"):
        if para_text.strip():
            story.append(Paragraph(para_text.strip(), exec_style))
            story.append(Spacer(1, 0.15 * cm))
    story.append(Spacer(1, 0.3 * cm))

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
    has_shifts = any(a.hot_seat_savings > 0 for a in allocs)

    if has_shifts:
        alloc_header = ["Unit", "Priority", "Demand", "Night HC", "Physical", "Saved", "Allocated", "Gap", "Risk"]
        alloc_col_widths = ["18%", "10%", "10%", "10%", "10%", "9%", "11%", "10%", "12%"]
    else:
        alloc_header = ["Unit", "Priority", "Policy Demand", "Allocated", "Gap", "Alloc %", "Risk"]
        alloc_col_widths = ["28%", "12%", "13%", "13%", "10%", "12%", "12%"]

    alloc_data = []
    alloc_levels = []
    for a in allocs:
        u = unit_map.get(a.unit_name)
        gap_pct = a.seat_gap / a.effective_demand_seats if a.effective_demand_seats else 0
        level = _risk_level(gap_pct, a.fragmentation_score)
        alloc_levels.append(level)
        if has_shifts:
            night_hc = str(a.night_demand) if a.night_demand > 0 else "—"
            alloc_data.append([
                a.unit_name,
                (u.business_priority or "—") if u else "—",
                str(a.effective_demand_seats),
                night_hc,
                str(a.physical_demand),
                str(a.hot_seat_savings) if a.hot_seat_savings > 0 else "—",
                str(a.allocated_seats),
                f"{a.seat_gap:+d}",
                level,
            ])
        else:
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

    if has_shifts:
        story.append(Paragraph(
            "Night HC = night-shift seat demand. Physical = max(Day, Night) after hot-seating. "
            "Saved = seats freed via desk sharing.",
            caption))
        story.append(Spacer(1, 0.15 * cm))

    story.append(_std_table(
        alloc_header, alloc_data,
        alloc_col_widths,
        alloc_row_bg,
    ))

    # ── PAGE 3: FLOOR OCCUPANCY BY TOWER (stacked view) ──────────────────────
    story.append(PageBreak())
    story.append(_header_table("CPG Seat Planning Report",
                               scenario.name, report_date, styles))
    story.extend(_section_header("Floor Occupancy by Tower", styles))
    story.append(Paragraph(
        "Floors listed sequentially per tower. Each row shows unit allocations and available capacity. "
        "Excluded floors are marked separately.",
        caption))
    story.append(Spacer(1, 0.2 * cm))

    # Build lookup structures
    excluded_set = set(scenario.params.excluded_floors) if scenario.params.excluded_floors else set()
    floor_map_lookup = {f.floor_id: f for f in floors}

    # Group floors by tower (building-tower)
    from collections import defaultdict, OrderedDict
    tower_floors = defaultdict(list)
    for f in floors:
        tower_floors[f.tower_id].append(f)
    for tid in tower_floors:
        tower_floors[tid].sort(key=lambda f: f.floor_number)

    # Group assignments by floor_id
    assign_by_floor = defaultdict(list)
    if assignments:
        for a in assignments:
            fid = f"{a.tower_id}-F{a.floor_number}"
            assign_by_floor[fid].append(a)

    # Render one table per tower
    for tower_id in sorted(tower_floors.keys()):
        tower_floor_list = tower_floors[tower_id]
        bldg_name = tower_floor_list[0].building_name if tower_floor_list else ""
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            f"<b>{tower_id}</b> — {bldg_name}", bold))
        story.append(Spacer(1, 0.1 * cm))

        tw_header = ["Floor", "Status", "Total", "Used", "Avail", "Util %", "Units on Floor"]
        tw_data = []
        tw_row_styles = []  # track per-row styling

        for f in tower_floor_list:
            fid = f.floor_id
            if fid in excluded_set:
                tw_data.append([
                    f"F{f.floor_number}", "EXCLUDED", str(f.total_seats),
                    "—", "—", "—", "Floor excluded from planning",
                ])
                tw_row_styles.append("excluded")
            else:
                floor_assigns = assign_by_floor.get(fid, [])
                used = sum(a.seats_assigned for a in floor_assigns)
                avail = f.total_seats - used
                util = f"{used / f.total_seats:.0%}" if f.total_seats > 0 else "—"
                # Build unit summary: "Engineering (80), Sales (40)"
                unit_parts = sorted(
                    [(a.unit_name, a.seats_assigned) for a in floor_assigns],
                    key=lambda x: -x[1],
                )
                units_str = ", ".join(f"{n} ({s})" for n, s in unit_parts) if unit_parts else "Empty"
                tw_data.append([
                    f"F{f.floor_number}", "Active", str(f.total_seats),
                    str(used), str(avail), util, units_str,
                ])
                tw_row_styles.append("active")

        # Build table with custom styling
        all_rows = [tw_header] + tw_data
        t = Table(all_rows, colWidths=["8%", "11%", "8%", "8%", "8%", "8%", "49%"], repeatRows=1)
        style_cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ]
        for i, row_style in enumerate(tw_row_styles):
            row_idx = i + 1  # offset for header
            if row_style == "excluded":
                style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx),
                                   colors.HexColor("#F0D0D0")))
                style_cmds.append(("TEXTCOLOR", (0, row_idx), (-1, row_idx),
                                   colors.HexColor("#8B0000")))
            else:
                style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx),
                                   GREY_ROW if i % 2 == 0 else WHITE))
        t.setStyle(TableStyle(style_cmds))
        story.append(t)

    # ── PAGE: FLOOR UTILIZATION MAPS ──────────────────────────────────────────
    if assignments:
        try:
            from components.floor_map import render_floor_map, _get_unit_color_map
            import plotly.io as pio

            # Build per-floor data
            floor_lookup = {f.floor_id: f.total_seats for f in floors}
            floor_assign_map = {}
            for a in assignments:
                fid = f"{a.tower_id}-F{a.floor_number}"
                if fid not in floor_assign_map:
                    floor_assign_map[fid] = {
                        "total_seats": floor_lookup.get(fid, 0),
                        "assignments": [],
                    }
                floor_assign_map[fid]["assignments"].append({
                    "unit_name": a.unit_name,
                    "seats_assigned": a.seats_assigned,
                })

            all_unit_names = list(set(a.unit_name for a in assignments))
            color_map = _get_unit_color_map(all_unit_names)

            story.append(PageBreak())
            story.append(_header_table("CPG Seat Planning Report",
                                       scenario.name, report_date, styles))
            story.extend(_section_header("Floor Utilization Maps", styles))
            story.append(Paragraph(
                "Each block represents a unit's seat allocation. Grey = available capacity.",
                caption))
            story.append(Spacer(1, 0.2 * cm))

            from reportlab.platypus import Image as RLImage

            map_images = []
            for fid in sorted(floor_assign_map.keys()):
                fdata = floor_assign_map[fid]
                fig = render_floor_map(
                    assignments=fdata["assignments"],
                    total_seats=fdata["total_seats"],
                    floor_label=fid,
                    unit_color_map=color_map,
                    height=200,
                )
                img_bytes = pio.to_image(fig, format="png", width=380, height=200, scale=2)
                img_io = io.BytesIO(img_bytes)
                map_images.append(RLImage(img_io, width=8.5 * cm, height=4.5 * cm))

            # Layout: 2 per row
            for i in range(0, len(map_images), 2):
                row_imgs = map_images[i:i + 2]
                if len(row_imgs) == 1:
                    row_imgs.append("")
                t = Table([row_imgs], colWidths=["50%", "50%"])
                t.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
        except Exception:
            # kaleido not installed or other error — skip floor maps
            pass

    # ── PAGE: RISKS & ALERTS ─────────────────────────────────────────────────
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

    # ── PAGE: DEMAND FORECAST SUMMARY ─────────────────────────────────────────
    if daily_attendance_df is not None:
        try:
            from engine.forecasting import compute_forecast_summary, compute_unit_trend

            unit_names_fc = sorted(daily_attendance_df["unit_name"].unique())
            summaries_fc = compute_forecast_summary(daily_attendance_df, unit_names_fc, forecast_months=6)

            if summaries_fc:
                story.append(PageBreak())
                story.append(_header_table("CPG Seat Planning Report",
                                           scenario.name, report_date, styles))
                story.extend(_section_header("Demand Forecast Summary", styles))
                story.append(Paragraph(
                    "Based on linear regression of daily in-office attendance data. "
                    "Forecasted values project the current trend forward 6 months. "
                    "Suggested Growth % is the annualised trend slope relative to current median.",
                    caption))
                story.append(Spacer(1, 0.3 * cm))

                fc_header = ["Unit", "Cur Median", "Cur Peak",
                             "Fcast Median (6m)", "Fcast Peak (6m)",
                             "Growth %", "Slope (seats/day)"]
                fc_col_widths = ["20%", "11%", "11%", "15%", "15%", "12%", "16%"]
                fc_data = []
                for s in summaries_fc:
                    trend_fc = compute_unit_trend(daily_attendance_df, s["unit_name"], forecast_months=6)
                    slope_str = f"{trend_fc['trend_slope']:+.3f}" if trend_fc else "—"
                    fc_data.append([
                        s["unit_name"],
                        str(s["current_median"]),
                        str(s["current_peak"]),
                        str(s["forecasted_median"]),
                        str(s["forecasted_peak"]),
                        f"{s['suggested_growth_pct']:.1%}",
                        slope_str,
                    ])

                def _fc_row_bg(i, row):
                    # Highlight positive growth in light green, negative in light amber
                    summaries_fc_sorted = summaries_fc
                    g = summaries_fc_sorted[i]["suggested_growth_pct"] if i < len(summaries_fc_sorted) else 0
                    if g > 0.05:
                        return colors.HexColor("#E8F5E9")
                    if g < -0.02:
                        return AMBER_BG
                    return GREY_ROW if i % 2 == 0 else WHITE

                story.append(_std_table(fc_header, fc_data, fc_col_widths, _fc_row_bg))
        except Exception:
            pass  # Graceful degradation if forecasting fails

    # ── PAGE: SCENARIO COMPARISON MATRIX ──────────────────────────────────────
    if matrix_results:
        try:
            from engine.scenario_comparison import get_best_scenario, build_explanation

            story.append(PageBreak())
            story.append(_header_table("CPG Seat Planning Report",
                                       scenario.name, report_date, styles))
            story.extend(_section_header("Scenario Comparison Matrix", styles))
            story.append(Paragraph(
                "All parameter combinations were automatically run through the full simulation "
                "and optimization pipeline. Ranked by composite score: "
                "headroom (35%), gap (35%), fragmentation (15%), consolidation (15%).",
                caption))
            story.append(Spacer(1, 0.3 * cm))

            # Best scenario callout box
            best_cmp = get_best_scenario(matrix_results)
            if best_cmp and not best_cmp.get("opt_status", "").startswith("Error"):
                obj_short = {
                    "optimal_placement": "Optimal Placement",
                    "rto_based": "RTO-Based",
                    "rto_whatif": "What-If RTO",
                }.get(best_cmp.get("objective", ""), best_cmp.get("objective", ""))
                alloc_str = (f"Alloc {best_cmp['alloc_pct']:.0%}, "
                             if best_cmp.get("alloc_pct") is not None else "")
                best_text = (
                    f"<b>Best Scenario #{best_cmp['rank']}:</b> "
                    f"{alloc_str}"
                    f"RTO {best_cmp['rto_mandate']:.1f}d/wk, "
                    f"Cap Red {best_cmp['cap_red']:.0%}, {obj_short}  —  "
                    f"{build_explanation(best_cmp)}"
                )
                best_style = ParagraphStyle(
                    "best_cmp", parent=body,
                    fontSize=9, leading=13,
                    backColor=GREEN_BG,
                    borderPadding=8, spaceBefore=4, spaceAfter=8,
                )
                story.append(Paragraph(best_text, best_style))
                story.append(Spacer(1, 0.3 * cm))

            # Ranked table
            cmp_header = ["Rank", "Alloc %", "RTO", "Cap Red", "Mode",
                          "Demand", "Capacity", "Headroom", "Gap",
                          "Opt Seats", "Floors", "Score"]
            cmp_col_widths = ["7%", "8%", "7%", "8%", "11%",
                              "8%", "8%", "9%", "8%",
                              "9%", "7%", "10%"]

            obj_abbr = {
                "optimal_placement": "Optimal",
                "rto_based": "RTO-Based",
                "rto_whatif": "What-If",
            }
            cmp_data = []
            for r in matrix_results:
                cmp_data.append([
                    str(r.get("rank", "—")),
                    f"{r['alloc_pct']:.0%}" if r.get("alloc_pct") is not None else "N/A",
                    f"{r['rto_mandate']:.1f}d",
                    f"{r.get('cap_red', 0):.0%}",
                    obj_abbr.get(r.get("objective", ""), r.get("objective", "—")),
                    f"{r.get('demand', 0):,}",
                    f"{r.get('capacity', 0):,}",
                    f"{r.get('headroom', 0):+,}",
                    f"{r.get('total_gap', 0):+,}",
                    f"{r.get('opt_seats', 0):,}",
                    str(r.get("floors_used", "—")),
                    f"{r.get('composite_score', 0):.3f}",
                ])

            def _cmp_row_bg(i, row):
                r = matrix_results[i]
                if r.get("rank") == 1:
                    return GREEN_BG
                if r.get("opt_status", "").startswith("Error"):
                    return RED_BG
                return GREY_ROW if i % 2 == 0 else WHITE

            story.append(_std_table(cmp_header, cmp_data, cmp_col_widths, _cmp_row_bg))
        except Exception:
            pass  # Graceful degradation

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
