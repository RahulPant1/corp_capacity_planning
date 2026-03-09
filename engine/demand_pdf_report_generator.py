"""Demand Analytics PDF Report Generator.

Produces a professional multi-page PDF using reportlab.platypus.
Returns bytes for st.download_button. Follows the same pattern as pdf_report_generator.py.
"""

import io
import math
from datetime import datetime
from typing import Optional, List

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)

from config.defaults import FORECAST_CAPACITY_ALERT_THRESHOLD


# ── Colour palette (matches existing PDF reports) ─────────────────────────────
NAVY       = colors.HexColor("#1E3A5F")
NAVY_LIGHT = colors.HexColor("#2E5090")
RED_BG     = colors.HexColor("#FFCCCC")
AMBER_BG   = colors.HexColor("#FFF3CC")
GREEN_BG   = colors.HexColor("#CCFFCC")
BLUE_BG    = colors.HexColor("#EBF5FF")
GREY_ROW   = colors.HexColor("#F5F5F5")
WHITE      = colors.white
BLACK      = colors.black
DARK_GREY  = colors.HexColor("#333333")


# ── ReportLab helpers (mirrors pdf_report_generator.py helpers) ───────────────

def _styles():
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("dah1", parent=base["Heading1"],
                         textColor=WHITE, fontSize=16, leading=20, spaceAfter=4)
    h2 = ParagraphStyle("dah2", parent=base["Heading2"],
                         textColor=NAVY, fontSize=13, leading=16,
                         spaceAfter=6, spaceBefore=10)
    body = ParagraphStyle("dabody", parent=base["Normal"],
                          fontSize=9, leading=13, textColor=DARK_GREY)
    caption = ParagraphStyle("dacaption", parent=base["Normal"],
                              fontSize=8, leading=11,
                              textColor=colors.HexColor("#666666"))
    bold = ParagraphStyle("dabold", parent=base["Normal"],
                          fontSize=9, leading=13, fontName="Helvetica-Bold")
    kpi_val = ParagraphStyle("dakpiv", parent=base["Normal"],
                              fontSize=18, leading=22, fontName="Helvetica-Bold",
                              textColor=NAVY, alignment=1)
    kpi_lbl = ParagraphStyle("dakpil", parent=base["Normal"],
                              fontSize=8, leading=10, alignment=1,
                              textColor=colors.HexColor("#555555"))
    return h1, h2, body, caption, bold, kpi_val, kpi_lbl


def _header_table(title: str, subtitle: str, report_date: str, styles):
    h1, *_ = styles
    data = [[
        Paragraph(f"<b>{title}</b>", h1),
        Paragraph(f"<b>{subtitle}</b><br/>{report_date}", h1),
    ]]
    t = Table(data, colWidths=["60%", "40%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, -1), WHITE),
        ("ALIGN",         (1, 0),  (1, 0),  "RIGHT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
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
    """Build a standard table with navy header and alternating / risk-colored rows."""
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


def _kpi_row(values, styles):
    """4-cell KPI card row."""
    _, _, _, _, _, kpi_val, kpi_lbl = styles

    def _cell(val_str, label):
        return [Paragraph(val_str, kpi_val), Paragraph(label, kpi_lbl)]

    n = len(values)
    data = [[_cell(v, l) for v, l in values]]
    t = Table(data, colWidths=[f"{100/n}%" for _ in values])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0F4FA")),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(
        1.5 * cm, 1 * cm,
        f"Demand Analytics Report — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    canvas.drawRightString(
        A4[0] - 1.5 * cm, 1 * cm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


# ── Page builders ─────────────────────────────────────────────────────────────

def _page_executive_summary(summaries, stf_results, alert_days, conflict, breach_data, clusters, styles):
    _, h2, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Executive Summary", styles)

    # KPI row
    total_current = sum(s.get("current_median", 0) for s in (summaries or []))
    total_forecast = sum(s.get("forecasted_median", 0) for s in (summaries or []))
    risk_days = len(alert_days) if alert_days else 0
    high_risk_count = sum(
        1 for d in (breach_data or []) if d.get("breach_probability", 0) >= 0.20
    )

    story.append(
        _kpi_row([
            (f"{total_current:,}", "Current Demand (Median Seats)"),
            (f"{total_forecast:,}", "Forecasted Demand (6 months)"),
            (str(risk_days), "Capacity Risk Days (>90%)"),
            (str(high_risk_count), "High Breach-Risk Units"),
        ], styles)
    )
    story.append(Spacer(1, 0.4 * cm))

    # Key metrics table
    overloaded = (conflict or {}).get("overloaded_days", [])
    stagger_units = [s.get("unit_name", "") for s in (conflict or {}).get("suggestions", [])]
    high_risk_names = [d.get("unit_name", "") for d in (breach_data or []) if d.get("breach_probability", 0) >= 0.20]

    overall_growth = (
        (total_forecast - total_current) / total_current * 100
        if total_current > 0 else 0.0
    )

    metrics = [
        ("Units Analysed", str(len(summaries) if summaries else 0)),
        ("Overall Growth Direction", f"{overall_growth:+.1f}%"),
        ("Overloaded DOW Days", ", ".join(overloaded) if overloaded else "None"),
        ("Attendance Groups", str(len(set(c.get("cluster_id") for c in (clusters or []))))),
    ]
    metric_rows = [[Paragraph(k, bold), Paragraph(v, body)] for k, v in metrics]
    metric_table = _std_table(
        [Paragraph("Metric", bold), Paragraph("Value", bold)],
        metric_rows,
        ["45%", "55%"],
    )
    story.append(metric_table)
    story.append(Spacer(1, 0.4 * cm))

    # Action items
    story += _section_header("Priority Actions", styles)
    actions = []
    if high_risk_names:
        actions.append(f"Add seats or increase allocation for: {', '.join(high_risk_names)} (high breach risk ≥20%).")
    if stagger_units:
        actions.append(f"Discuss RTO day staggering with: {', '.join(stagger_units)} to reduce peak-day crowding.")
    if risk_days > 0:
        actions.append(f"{risk_days} day(s) in the short-term forecast exceed 90% capacity — review Overflow Planning page.")
    if not actions:
        actions.append("No urgent actions required. Monitor trends monthly.")

    for action in actions:
        story.append(Paragraph(f"• {action}", body))
        story.append(Spacer(1, 0.15 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "See subsequent pages for detailed analysis: Forecast Summary → Short-Term Forecast → "
        "DOW Patterns → Capacity Breach Risk → Load Balancing → Overflow Planning → Temporal Clusters.",
        caption,
    ))
    return story


def _page_forecast_summary(summaries, forecast_months, styles):
    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header(f"Forecast Summary — All Units ({forecast_months}-Month Horizon)", styles)

    if not summaries:
        story.append(Paragraph("Insufficient data — need ≥7 days per unit.", body))
        return story

    def _action(s):
        pct = s.get("six_month_change_pct", 0)
        direction = s.get("trend_direction", "")
        change = s.get("six_month_change", 0)
        growth = s.get("suggested_growth_pct", 0)
        if "Growing" in direction and pct > 10:
            return f"Add ~{change} seats. Apply {growth:.0%} growth in What-If."
        elif "Declining" in direction and pct < -5:
            return f"Consider releasing {abs(change)} seats."
        return "No immediate action."

    def _row_bg(idx, row):
        cell_val = str(row[6]) if len(row) > 6 else ""
        if "Growing" in cell_val:
            return colors.HexColor("#E8F5E9")
        if "Declining" in cell_val:
            return AMBER_BG
        return GREY_ROW if idx % 2 == 0 else WHITE

    hdrs = ["Unit", "Curr Median", "Curr Peak", f"Fcast {forecast_months}m", "6M Change", "6M %", "Trend", "Action"]
    header_row = [Paragraph(h, bold) for h in hdrs]

    data_rows = []
    for s in summaries:
        pct = s.get("six_month_change_pct", 0)
        change = s.get("six_month_change", 0)
        data_rows.append([
            Paragraph(s.get("unit_name", ""), body),
            Paragraph(str(s.get("current_median", 0)), body),
            Paragraph(str(s.get("current_peak", 0)), body),
            Paragraph(str(s.get("forecasted_median", 0)), body),
            Paragraph(f"{change:+}", body),
            Paragraph(f"{pct:+.1f}%", body),
            Paragraph(s.get("trend_direction", ""), body),
            Paragraph(_action(s), body),
        ])

    col_widths = ["15%", "9%", "9%", "9%", "9%", "8%", "13%", "28%"]
    story.append(_std_table(header_row, data_rows, col_widths, row_bg_fn=_row_bg))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Apply the 'Suggested Growth %' column in What-If Analysis → Unit Overrides to push these forecasts into the seat allocation engine.",
        caption,
    ))
    return story


def _page_short_term_forecast(stf_results, alert_days, styles):
    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Short-Term Seat Demand Forecast", styles)

    if not stf_results:
        story.append(Paragraph("Need ≥7 days of data to generate short-term forecast.", body))
        return story

    # Alert callout
    if alert_days:
        alert_text = (
            f"<b>CAPACITY ALERT:</b> {len(alert_days)} day(s) exceed 90% capacity. "
            "Activate overflow floors on these days. See Overflow Planning page."
        )
        alert_data = [[Paragraph(alert_text, body)]]
        alert_table = Table(alert_data, colWidths=["100%"])
        alert_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), RED_BG),
            ("BOX",        (0, 0), (-1, -1), 1, colors.HexColor("#CC0000")),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ]))
        story.append(alert_table)
        story.append(Spacer(1, 0.3 * cm))

    def _row_bg(idx, row):
        label = str(row[4]) if len(row) > 4 else ""
        if "ALERT" in label:
            return RED_BG
        if "WATCH" in label:
            return AMBER_BG
        return GREY_ROW if idx % 2 == 0 else WHITE

    hdrs = ["Period", "Day", "Expected Seats", "Capacity %", "Risk", "Recommended Action"]
    header_row = [Paragraph(h, bold) for h in hdrs]

    data_rows = []
    for r in stf_results:
        pct = r.get("capacity_pct", 0)
        risk_flag = "ALERT" if pct > FORECAST_CAPACITY_ALERT_THRESHOLD else ("WATCH" if pct > 0.65 else "OK")
        day = r.get("weekday_name", "")
        if pct > FORECAST_CAPACITY_ALERT_THRESHOLD:
            action = f"Activate overflow floors on {day}."
        elif pct > 0.65:
            action = "Monitor — coordinate with Facilities."
        else:
            action = "No action required."
        data_rows.append([
            Paragraph(r.get("short_label", ""), body),
            Paragraph(day, body),
            Paragraph(str(r.get("expected_seats", 0)), body),
            Paragraph(f"{pct:.0%}", body),
            Paragraph(risk_flag, body),
            Paragraph(action, body),
        ])

    story.append(_std_table(header_row, data_rows, ["13%", "10%", "13%", "10%", "10%", "44%"], row_bg_fn=_row_bg))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Red = >90% capacity risk. Amber = >65%. Coordinate with Facilities for temporary overflow "
        "desk access on ALERT days — no permanent reassignment needed.",
        caption,
    ))
    return story


def _page_dow_patterns(dow_df, styles):
    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Day-of-Week Attendance Patterns", styles)

    if dow_df is None or dow_df.empty:
        story.append(Paragraph("No DOW data available.", body))
        return story

    # Pivot: unit × day (median)
    try:
        day_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        pivot = dow_df.pivot_table(
            index="unit_name", columns="day_name",
            values="median_count", aggfunc="sum",
        )
        pivot_cols = [d for d in day_order if d in pivot.columns]
        pivot = pivot[pivot_cols].reset_index()
        pivot.rename(columns={"unit_name": "Unit"}, inplace=True)

        def _row_bg_dow(idx, row):
            return GREY_ROW if idx % 2 == 0 else WHITE

        hdrs_pivot = list(pivot.columns)
        header_row = [Paragraph(h, bold) for h in hdrs_pivot]
        data_rows = []
        for _, row_data in pivot.iterrows():
            # Find peak day
            day_vals = {col: row_data.get(col, 0) for col in pivot_cols if col in row_data}
            peak_col = max(day_vals, key=day_vals.get) if day_vals else None
            pdf_row = []
            for col in hdrs_pivot:
                val = row_data.get(col, "")
                val_str = str(round(val)) if isinstance(val, (int, float)) else str(val)
                if col == peak_col:
                    pdf_row.append(Paragraph(f"<b>{val_str} ◀</b>", body))
                else:
                    pdf_row.append(Paragraph(val_str, body))
            data_rows.append(pdf_row)

        n_cols = len(hdrs_pivot)
        col_widths = [f"{100/n_cols:.1f}%" for _ in hdrs_pivot]
        story.append(_std_table(header_row, data_rows, col_widths, row_bg_fn=_row_bg_dow))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            "◀ marks the peak attendance day per unit. Units sharing the same peak day create "
            "floor crowding — consider staggering their RTO anchor days. See Load Balancing page.",
            caption,
        ))
    except Exception:
        story.append(Paragraph("Unable to build DOW pivot. Raw data may be insufficient.", body))

    return story


def _page_capacity_breach(breach_data, styles):
    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Capacity Breach Risk", styles)

    if not breach_data:
        story.append(Paragraph(
            "No breach data available. Run a Policy Simulation in What-If Analysis first.",
            body,
        ))
        return story

    def _tier(prob):
        if prob >= 0.20:
            return "High"
        if prob >= 0.10:
            return "Medium"
        return "Low"

    def _action(d):
        prob = d.get("breach_probability", 0)
        mag = d.get("avg_breach_magnitude", 0)
        seats = math.ceil(mag / 5) * 5 if mag > 0 else 0
        name = d.get("unit_name", "")
        if prob >= 0.20:
            return f"HIGH: Add {seats} seats in What-If."
        elif prob >= 0.10:
            return f"MONITOR: Consider +{seats} seats."
        return "Low risk — no action."

    def _row_bg_breach(idx, row):
        tier = str(row[0]) if row else ""
        if "High" in tier:
            return RED_BG
        if "Medium" in tier:
            return AMBER_BG
        return GREEN_BG

    sorted_data = sorted(
        breach_data,
        key=lambda d: {"High": 0, "Medium": 1, "Low": 2}.get(_tier(d.get("breach_probability", 0)), 3),
    )

    hdrs = ["Risk", "Unit", "Allocated", "Breach %", "Overflow Days/Mo", "Avg Overflow", "Add Seats", "Action"]
    header_row = [Paragraph(h, bold) for h in hdrs]
    data_rows = []
    for d in sorted_data:
        prob = d.get("breach_probability", 0)
        mag = d.get("avg_breach_magnitude", 0)
        data_rows.append([
            Paragraph(_tier(prob), body),
            Paragraph(d.get("unit_name", ""), body),
            Paragraph(str(d.get("allocated_seats", 0)), body),
            Paragraph(f"{prob:.0%}", body),
            Paragraph(str(round(d.get("expected_breach_days_per_month", 0), 1)), body),
            Paragraph(str(round(mag, 1)), body),
            Paragraph(str(math.ceil(mag / 5) * 5 if mag > 0 else 0), body),
            Paragraph(_action(d), body),
        ])

    story.append(_std_table(header_row, data_rows, ["8%", "14%", "9%", "8%", "12%", "10%", "9%", "30%"],
                             row_bg_fn=_row_bg_breach))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "High = ≥20% of working days attendance exceeds allocation. "
        "'Add Seats' is rounded up to nearest 5 based on average overflow size.",
        caption,
    ))
    return story


def _page_load_balancing(conflict, peak_data, styles):
    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Peak Day Load Balancing Advisory", styles)

    if not conflict:
        story.append(Paragraph("No DOW conflict data available.", body))
        return story

    day_loads = conflict.get("day_loads", {})
    overloaded = set(conflict.get("overloaded_days", []))
    suggestions = conflict.get("suggestions", [])

    # Daily load table
    if day_loads:
        def _row_bg_load(idx, row):
            status = str(row[2]) if len(row) > 2 else ""
            return AMBER_BG if "OVERLOADED" in status else (GREY_ROW if idx % 2 == 0 else WHITE)

        hdrs = ["Day", "Total Expected Seats", "Status"]
        header_row = [Paragraph(h, bold) for h in hdrs]
        data_rows = [
            [
                Paragraph(day, body),
                Paragraph(str(round(seats)), body),
                Paragraph("OVERLOADED" if day in overloaded else "Normal", body),
            ]
            for day, seats in day_loads.items()
        ]
        story.append(_std_table(header_row, data_rows, ["30%", "40%", "30%"], row_bg_fn=_row_bg_load))
        story.append(Spacer(1, 0.3 * cm))

    # Stagger suggestions
    story += _section_header("Stagger Suggestions", styles)
    if suggestions:
        def _row_bg_sug(idx, row):
            return AMBER_BG if idx % 2 == 0 else WHITE

        hdrs_s = ["Unit", "Current Peak", "Suggested Day", "Load Reduction", "Recommended Action"]
        header_row_s = [Paragraph(h, bold) for h in hdrs_s]
        data_rows_s = []
        for s in suggestions:
            reduction = s.get("load_reduction", s.get("est_load_moved", 0))
            action = (
                f"Discuss with {s.get('unit_name', '')} manager: shift RTO anchor "
                f"from {s.get('current_peak_day', '')} to {s.get('suggested_day', '')}. "
                f"Estimated relief: {round(reduction)} seats off peak day."
            )
            data_rows_s.append([
                Paragraph(s.get("unit_name", ""), body),
                Paragraph(s.get("current_peak_day", ""), body),
                Paragraph(s.get("suggested_day", ""), body),
                Paragraph(str(round(reduction)), body),
                Paragraph(action, body),
            ])
        story.append(_std_table(header_row_s, data_rows_s, ["14%", "11%", "11%", "12%", "52%"],
                                 row_bg_fn=_row_bg_sug))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            "These are advisory suggestions only — share with unit managers for voluntary RTO anchor day coordination.",
            caption,
        ))
    elif overloaded:
        story.append(Paragraph(
            "Overloaded days detected but no specific stagger suggestions generated. "
            "Review unit attendance schedules manually.",
            body,
        ))
    else:
        story.append(Paragraph(
            "Load is balanced across the week — no stagger action required.",
            body,
        ))

    return story


def _page_overflow_planning(alert_days, scenario, floors, styles):
    from engine.spatial import get_floor_utilization

    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Peak Day Overflow Planning", styles)

    if not (alert_days and getattr(scenario, "floor_assignments", None)
            and getattr(scenario, "allocation_results", None)):
        story.append(Paragraph(
            "Run a Policy Simulation in What-If Analysis first to see floor-level overflow options.",
            body,
        ))
        return story

    floor_util = get_floor_utilization(floors or [], scenario.floor_assignments)
    flex_floors = sorted(
        [f for f in floor_util if f.get("available_seats", 0) > 0],
        key=lambda f: f["available_seats"], reverse=True,
    )
    at_risk = sorted(
        [a for a in scenario.allocation_results if getattr(a, "seat_gap", 0) < 0],
        key=lambda a: getattr(a, "seat_gap", 0),
    )
    overflow_cap = sum(f["available_seats"] for f in flex_floors)

    # Alert days
    story.append(Paragraph("<b>Capacity Risk Days:</b>", body))
    alert_rows = [
        [
            Paragraph(r.get("weekday_name", ""), body),
            Paragraph(str(r.get("expected_seats", 0)), body),
            Paragraph(f"{r.get('capacity_pct', 0):.0%}", body),
        ]
        for r in alert_days
    ]
    alert_table = _std_table(
        [Paragraph(h, bold) for h in ["Day", "Expected Seats", "Capacity %"]],
        alert_rows, ["33%", "33%", "34%"],
        row_bg_fn=lambda i, r: RED_BG,
    )
    story.append(alert_table)
    story.append(Spacer(1, 0.3 * cm))

    # Overflow floors
    story.append(Paragraph("<b>Available Overflow Floors</b> (spare unallocated seats):", body))
    if flex_floors:
        floor_rows = [
            [
                Paragraph(f.get("floor_id", ""), body),
                Paragraph(f.get("tower_id", ""), body),
                Paragraph(f.get("building_name", ""), body),
                Paragraph(str(f.get("available_seats", 0)), body),
                Paragraph(f"{f.get('utilization_pct', 0):.0%}", body),
            ]
            for f in flex_floors
        ]
        floor_table = _std_table(
            [Paragraph(h, bold) for h in ["Floor", "Tower", "Building", "Spare Seats", "Utilization %"]],
            floor_rows, ["20%", "15%", "25%", "20%", "20%"],
            row_bg_fn=lambda i, r: GREEN_BG if i % 2 == 0 else WHITE,
        )
        story.append(floor_table)
    else:
        story.append(Paragraph("No floors have spare capacity — consider adding capacity in What-If Analysis.", body))

    story.append(Spacer(1, 0.3 * cm))

    # At-risk units
    if at_risk:
        story.append(Paragraph("<b>Units with Seat Shortfall</b> (demand > current allocation):", body))
        risk_rows = []
        for a in at_risk:
            gap = getattr(a, "seat_gap", 0)
            needed = abs(gap)
            if overflow_cap >= needed and flex_floors:
                action = f"Direct {needed} staff to {flex_floors[0]['floor_id']} on peak days."
            else:
                action = f"Insufficient overflow ({overflow_cap} available, {needed} needed). Escalate to Facilities."
            risk_rows.append([
                Paragraph(getattr(a, "unit_name", ""), body),
                Paragraph(str(getattr(a, "allocated_seats", 0)), body),
                Paragraph(str(getattr(a, "effective_demand_seats", 0)), body),
                Paragraph(str(gap), body),
                Paragraph(action, body),
            ])
        risk_table = _std_table(
            [Paragraph(h, bold) for h in ["Unit", "Allocated", "Demand", "Gap", "Priority Action"]],
            risk_rows, ["15%", "12%", "12%", "8%", "53%"],
            row_bg_fn=lambda i, r: RED_BG,
        )
        story.append(risk_table)
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            "Coordinate with Facilities for temporary flex desk access on peak days for shortfall units. "
            "No permanent reassignment required — day-specific overflow arrangements only.",
            caption,
        ))

    return story


def _page_temporal_clusters(clusters, dow_df, scenario, styles):
    _, _, body, caption, bold, *_ = styles
    story = []
    story += _section_header("Temporal Clusters — Unit Attendance Groups", styles)

    if not clusters:
        story.append(Paragraph("Insufficient data for clustering (need ≥2 units).", body))
        return story

    # Build peak day map
    peak_day_map: dict = {}
    if dow_df is not None and not dow_df.empty and "unit_name" in dow_df.columns:
        for unit in dow_df["unit_name"].unique():
            udf = dow_df[dow_df["unit_name"] == unit]
            if not udf.empty:
                peak_day_map[unit] = udf.loc[udf["median_count"].idxmax()].get("day_name", "N/A")

    # Build cluster groups
    cluster_groups: dict = {}
    for r in clusters:
        label = r.get("cluster_label", "")
        cluster_groups.setdefault(label, []).append(r.get("unit_name", ""))

    # Cluster assignment table
    palette_bg = [
        colors.HexColor("#BBDEFB"), colors.HexColor("#FFCCBC"),
        colors.HexColor("#C8E6C9"), colors.HexColor("#E1BEE7"),
        colors.HexColor("#FFF9C4"), colors.HexColor("#B2EBF2"),
    ]
    cluster_ids = sorted(set(r.get("cluster_id", 0) for r in clusters))
    cluster_color = {cid: palette_bg[i % len(palette_bg)] for i, cid in enumerate(cluster_ids)}

    def _row_bg_cluster(idx, row):
        # Can't access cluster_id from row directly here; use alternating as fallback
        return GREY_ROW if idx % 2 == 0 else WHITE

    hdrs = ["Unit", "Group", "Group Size", "Peak Day", "Planning Note"]
    header_row = [Paragraph(h, bold) for h in hdrs]
    data_rows = []
    for r in clusters:
        unit = r.get("unit_name", "")
        label = r.get("cluster_label", "")
        peers = [m for m in cluster_groups.get(label, []) if m != unit]
        note = (
            f"Do NOT co-locate with: {', '.join(peers)}. Enable Cluster-Diverse Placement in What-If."
            if peers else "Sole member — no same-floor constraint."
        )
        data_rows.append([
            Paragraph(unit, body),
            Paragraph(label, body),
            Paragraph(str(len(cluster_groups.get(label, []))), body),
            Paragraph(peak_day_map.get(unit, "N/A"), body),
            Paragraph(note, body),
        ])

    # Apply cluster-color backgrounds
    all_rows_pdf = [header_row] + data_rows
    t = Table(all_rows_pdf, colWidths=["16%", "10%", "10%", "10%", "54%"], repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
    ]
    for i, r in enumerate(clusters, start=1):
        cid = r.get("cluster_id", 0)
        bg = cluster_color.get(cid, WHITE)
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Units in the same group peak simultaneously — avoid co-locating them on the same floor. "
        "Enable 'Cluster-Diverse Placement' in What-If Analysis → Cluster Settings to automate this.",
        caption,
    ))

    # Floor advisory (if scenario has floor_assignments)
    if scenario and getattr(scenario, "floor_assignments", None):
        story.append(Spacer(1, 0.3 * cm))
        story += _section_header("Floor Cluster Diversity Advisory", styles)
        try:
            cluster_map = {r.get("unit_name", ""): r.get("cluster_id") for r in clusters}
            floor_groups: dict = {}
            for fa in scenario.floor_assignments:
                fid = f"{fa.tower_id}-F{fa.floor_number}"
                cid = cluster_map.get(fa.unit_name)
                floor_groups.setdefault(fid, {"units": [], "clusters": set()})
                floor_groups[fid]["units"].append(fa.unit_name)
                if cid is not None:
                    floor_groups[fid]["clusters"].add(cid)

            adv_rows = []
            for fid, info in sorted(floor_groups.items()):
                n_clusters = len(info["clusters"])
                risk = "⚠️ Concentrated" if n_clusters <= 1 else "✅ Diversified"
                rec = (
                    "Re-assign a unit from a different group. Enable Cluster-Diverse Placement in What-If."
                    if n_clusters <= 1 else "No action — groups are well-mixed."
                )
                adv_rows.append([
                    Paragraph(fid, body),
                    Paragraph(", ".join(info["units"]), body),
                    Paragraph(str(n_clusters), body),
                    Paragraph(risk, body),
                    Paragraph(rec, body),
                ])

            def _row_bg_adv(idx, row):
                label = str(row[3]) if len(row) > 3 else ""
                return AMBER_BG if "Concentrated" in label else (GREY_ROW if idx % 2 == 0 else WHITE)

            story.append(_std_table(
                [Paragraph(h, bold) for h in ["Floor", "Units", "Groups", "Status", "Recommendation"]],
                adv_rows, ["12%", "30%", "9%", "16%", "33%"],
                row_bg_fn=_row_bg_adv,
            ))
        except Exception:
            pass

    return story


# ── Public entry point ────────────────────────────────────────────────────────

def generate_demand_pdf_report(
    daily_df,
    unit_names: list,
    rule_config: dict,
    forecast_months: int = 6,
    summaries: Optional[list] = None,
    stf_results: Optional[list] = None,
    alert_days: Optional[list] = None,
    dow_df=None,
    conflict: Optional[dict] = None,
    peak_data: Optional[list] = None,
    breach_data: Optional[list] = None,
    clusters: Optional[list] = None,
    scenario=None,
    floors: Optional[list] = None,
) -> bytes:
    """Generate a comprehensive Demand Analytics PDF report.

    Returns bytes suitable for st.download_button.
    """
    output = io.BytesIO()
    story = []
    styles = _styles()
    report_date = datetime.now().strftime("%B %d, %Y")

    story.append(_header_table(
        "Demand Analytics Report", "Attendance Intelligence", report_date, styles
    ))
    story.append(Spacer(1, 0.3 * cm))

    try:
        story += _page_executive_summary(
            summaries, stf_results, alert_days, conflict, breach_data or [], clusters, styles
        )
    except Exception:
        pass

    story.append(PageBreak())

    try:
        story += _page_forecast_summary(summaries, forecast_months, styles)
    except Exception:
        pass

    if stf_results:
        story.append(PageBreak())
        try:
            story += _page_short_term_forecast(stf_results, alert_days, styles)
        except Exception:
            pass

    if dow_df is not None and not (hasattr(dow_df, "empty") and dow_df.empty):
        story.append(PageBreak())
        try:
            story += _page_dow_patterns(dow_df, styles)
        except Exception:
            pass

    if breach_data:
        story.append(PageBreak())
        try:
            story += _page_capacity_breach(breach_data, styles)
        except Exception:
            pass

    if conflict:
        story.append(PageBreak())
        try:
            story += _page_load_balancing(conflict, peak_data, styles)
        except Exception:
            pass

    if alert_days and scenario and getattr(scenario, "floor_assignments", None):
        story.append(PageBreak())
        try:
            story += _page_overflow_planning(alert_days, scenario, floors, styles)
        except Exception:
            pass

    if clusters:
        story.append(PageBreak())
        try:
            story += _page_temporal_clusters(clusters, dow_df, scenario, styles)
        except Exception:
            pass

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
