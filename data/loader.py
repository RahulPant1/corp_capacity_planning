"""File upload parsing — CSV/XLSX into typed model lists."""

import pandas as pd
from typing import List, Tuple
from models.building import Floor
from models.unit import Unit
from models.attendance import AttendanceProfile


def parse_buildings(df: pd.DataFrame) -> List[Floor]:
    """Convert a buildings DataFrame into Floor objects."""
    floors = []
    for _, row in df.iterrows():
        floors.append(Floor(
            building_id=str(row["Building ID"]).strip(),
            building_name=str(row["Building Name"]).strip(),
            tower_id=str(row["Tower ID"]).strip(),
            floor_number=int(row["Floor Number"]),
            total_seats=int(row["Total Seats"]),
        ))
    return floors


def parse_units(df: pd.DataFrame) -> List[Unit]:
    """Convert a units DataFrame into Unit objects."""
    units = []
    for _, row in df.iterrows():
        priority = None
        if "Business Priority" in df.columns and pd.notna(row.get("Business Priority")):
            priority = str(row["Business Priority"]).strip()
        units.append(Unit(
            unit_name=str(row["Unit Name"]).strip(),
            current_total_hc=int(row["Current Total Headcount"]),
            hc_growth_pct=float(row["HC Growth Forecast (%)"]) / 100.0,
            attrition_pct=float(row["Attrition Forecast (%)"]) / 100.0,
            business_priority=priority,
        ))
    return units


def parse_attendance(df: pd.DataFrame) -> List[AttendanceProfile]:
    """Convert an attendance DataFrame into AttendanceProfile objects."""
    profiles = []
    for _, row in df.iterrows():
        stability = None
        if "Attendance Stability" in df.columns and pd.notna(row.get("Attendance Stability")):
            stability = float(row["Attendance Stability"])
        profiles.append(AttendanceProfile(
            unit_name=str(row["Unit Name"]).strip(),
            monthly_median_hc=float(row["Monthly Median In-Office Strength"]),
            monthly_max_hc=float(row["Monthly Max In-Office Strength"]),
            avg_rto_days_per_week=float(row["Avg RTO Days/Week"]),
            attendance_stability=stability,
        ))
    return profiles


def load_file(uploaded_file) -> pd.DataFrame:
    """Load an uploaded file (CSV or XLSX) into a DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file format: {name}. Use CSV or XLSX.")


# Expected sheet names for multi-tab Excel (case-insensitive matching)
SHEET_ALIASES = {
    "buildings": ["buildings", "building", "building master", "building & floor master", "floors", "floor master"],
    "units": ["units", "unit", "unit headcount", "headcount", "hc", "unit hc", "unit headcount & forecast"],
    "attendance": ["attendance", "rto", "attendance & rto", "rto behavior", "attendance & rto behavior"],
}


def _match_sheet(sheet_names: List[str], category: str) -> str:
    """Find a sheet name matching the given category. Returns the matched name or raises."""
    aliases = SHEET_ALIASES[category]
    lower_map = {s.lower().strip(): s for s in sheet_names}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    raise ValueError(
        f"Could not find a sheet for '{category}'. "
        f"Expected one of: {aliases}. "
        f"Found sheets: {sheet_names}"
    )


def load_multi_sheet_excel(uploaded_file) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load a single Excel file with 3 tabs: Buildings, Units, Attendance.

    Sheet names are matched case-insensitively. Accepted names include:
    - Buildings: 'Buildings', 'Building Master', 'Floors', etc.
    - Units: 'Units', 'Headcount', 'Unit HC', etc.
    - Attendance: 'Attendance', 'RTO', 'Attendance & RTO', etc.

    Returns (buildings_df, units_df, attendance_df).
    """
    xl = pd.ExcelFile(uploaded_file, engine="openpyxl")
    sheet_names = xl.sheet_names

    buildings_sheet = _match_sheet(sheet_names, "buildings")
    units_sheet = _match_sheet(sheet_names, "units")
    attendance_sheet = _match_sheet(sheet_names, "attendance")

    buildings_df = pd.read_excel(xl, sheet_name=buildings_sheet)
    units_df = pd.read_excel(xl, sheet_name=units_sheet)
    attendance_df = pd.read_excel(xl, sheet_name=attendance_sheet)

    return buildings_df, units_df, attendance_df


def load_csv_path(path: str) -> pd.DataFrame:
    """Load a CSV file from a local path."""
    return pd.read_csv(path)
