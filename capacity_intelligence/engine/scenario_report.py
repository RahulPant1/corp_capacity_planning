"""Excel report generator for Scenario Planner impact results.

No Streamlit imports — pure pandas / openpyxl.

Usage::

    from engine.scenario_report import generate_scenario_excel_report

    xlsx_bytes = generate_scenario_excel_report(
        baseline_df=...,
        scenario_df=...,
        date_range=(start_date, end_date),
        scenario_kpis={...},
        building_impact_df=...,
        live_insights=[...],
        mode="Event Impact",
    )
    st.download_button("Download .xlsx", data=xlsx_bytes, ...)
"""

import io
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_scenario_excel_report(
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
    scenario_kpis: dict,
    building_impact_df: pd.DataFrame,
    live_insights: List[str],
    mode: str = "Event Impact",
    mode_params: Optional[Dict] = None,
) -> bytes:
    """Build and return xlsx bytes for the Scenario Impact Report.

    Sheets
    ------
    1. Summary        — KPI metrics + mode parameters
    2. Building Impact — per-building impact table
    3. Daily Data      — day-by-day baseline vs scenario footfall + delta
    4. Insights        — live insight bullets as structured rows
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _write_summary_sheet(writer, scenario_kpis, mode, mode_params, date_range)
        _write_building_impact_sheet(writer, building_impact_df)
        _write_daily_data_sheet(writer, baseline_df, scenario_df, date_range)
        _write_insights_sheet(writer, live_insights, mode)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Sheet writers
# ---------------------------------------------------------------------------

def _write_summary_sheet(
    writer: pd.ExcelWriter,
    kpis: dict,
    mode: str,
    mode_params: Optional[Dict],
    date_range: Tuple,
) -> None:
    start, end = date_range
    baseline_avg = kpis.get("baseline_avg_daily", 0)
    scenario_avg = kpis.get("scenario_avg_daily", 0)
    delta = scenario_avg - baseline_avg
    delta_pct = (delta / baseline_avg * 100) if baseline_avg else 0.0

    rows = [
        ("Report Type", mode),
        ("Event Start", str(start)),
        ("Event End", str(end)),
        ("Window (calendar days)", kpis.get("window_days", "")),
        ("Window (weekdays)", kpis.get("window_weekdays", "")),
        ("", ""),
        ("Baseline Avg Daily (seats/day)", baseline_avg),
        ("Scenario Avg Daily (seats/day)", scenario_avg),
        ("Delta (seats/day)", round(delta, 1)),
        ("Delta %", f"{delta_pct:+.1f}%"),
    ]

    if mode_params:
        rows.append(("", ""))
        rows.append(("Mode Parameters", ""))
        for k, v in mode_params.items():
            rows.append((str(k), str(v)))

    df = pd.DataFrame(rows, columns=["Metric", "Value"])
    df.to_excel(writer, sheet_name="Summary", index=False)
    _autofit(writer, "Summary", df)


def _write_building_impact_sheet(
    writer: pd.ExcelWriter,
    impact_df: pd.DataFrame,
) -> None:
    if impact_df is None or impact_df.empty:
        pd.DataFrame({"Note": ["No building impact data available."]}).to_excel(
            writer, sheet_name="Building Impact", index=False
        )
        return
    impact_df.to_excel(writer, sheet_name="Building Impact", index=False)
    _autofit(writer, "Building Impact", impact_df)


def _write_daily_data_sheet(
    writer: pd.ExcelWriter,
    baseline_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
    date_range: Tuple,
) -> None:
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1])

    date_col      = "Date" if "Date" in baseline_df.columns else "date"
    predicted_col = "Employee Count Predicted" if "Employee Count Predicted" in baseline_df.columns else "footfall"

    def daily_totals(df):
        sliced = df[(df[date_col] >= start_ts) & (df[date_col] <= end_ts)]
        return (
            sliced.groupby(date_col)
            .agg(predicted=(predicted_col, "sum"))
            .reset_index()
        )

    base_d = daily_totals(baseline_df).rename(columns={"predicted": "Baseline Predicted"})
    scen_d = daily_totals(scenario_df).rename(columns={"predicted": "Scenario Predicted"})
    merged = base_d.merge(scen_d, on=date_col, how="outer").sort_values(date_col)
    merged["Delta (seats)"] = merged["Scenario Predicted"] - merged["Baseline Predicted"]
    merged["Delta %"] = (
        (merged["Delta (seats)"] / merged["Baseline Predicted"].clip(lower=1)) * 100
    ).round(1)
    merged = merged.rename(columns={date_col: "Date"})
    merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d")
    merged.to_excel(writer, sheet_name="Daily Data", index=False)
    _autofit(writer, "Daily Data", merged)


def _write_insights_sheet(
    writer: pd.ExcelWriter,
    insights: List[str],
    mode: str,
) -> None:
    # Strip markdown bold markers and common emoji for clean Excel output
    def _clean(text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold** → bold
        text = re.sub(r"[^\x00-\x7F]", "", text).strip()  # remove non-ASCII (emoji)
        return text

    rows = [
        {"#": i + 1, "Insight": _clean(ins), "Mode": mode}
        for i, ins in enumerate(insights)
    ]
    df = pd.DataFrame(rows) if rows else pd.DataFrame({"Note": ["No insights available."]})
    df.to_excel(writer, sheet_name="Insights", index=False)
    _autofit(writer, "Insights", df)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _autofit(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    """Set column widths to fit content (approximate)."""
    try:
        ws = writer.sheets[sheet_name]
        for col_idx, col in enumerate(df.columns, start=1):
            max_len = max(
                len(str(col)),
                df[col].astype(str).str.len().max() if not df.empty else 0,
            )
            ws.column_dimensions[
                ws.cell(row=1, column=col_idx).column_letter
            ].width = min(max_len + 4, 60)
    except Exception:
        pass  # autofit is cosmetic; never crash on it
