"""Schema validation for uploaded data files."""

from dataclasses import dataclass, field
from typing import List
import pandas as pd


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


BUILDING_REQUIRED_COLUMNS = [
    "Building ID",
    "Building Name",
    "Tower ID",
    "Floor Number",
    "Total Seats",
]

UNIT_REQUIRED_COLUMNS = [
    "Unit Name",
    "Current Total Headcount",
    "HC Growth Forecast (%)",
    "Attrition Forecast (%)",
]

ATTENDANCE_REQUIRED_COLUMNS = [
    "Unit Name",
    "Monthly Median In-Office Strength",
    "Monthly Max In-Office Strength",
    "Avg RTO Days/Week",
]


def _check_required_columns(df: pd.DataFrame, required: List[str], file_label: str) -> ValidationResult:
    result = ValidationResult()
    missing = [col for col in required if col not in df.columns]
    if missing:
        result.is_valid = False
        result.errors.append(f"{file_label}: Missing required columns: {', '.join(missing)}")
    if df.empty:
        result.is_valid = False
        result.errors.append(f"{file_label}: File contains no data rows.")
    return result


def validate_buildings(df: pd.DataFrame) -> ValidationResult:
    result = _check_required_columns(df, BUILDING_REQUIRED_COLUMNS, "Building Master")
    if not result.is_valid:
        return result

    # Check for negative seats
    if (df["Total Seats"] < 0).any():
        result.is_valid = False
        result.errors.append("Building Master: Total Seats cannot be negative.")

    # Check for duplicate floor entries
    dupes = df.duplicated(subset=["Tower ID", "Floor Number"], keep=False)
    if dupes.any():
        result.is_valid = False
        dupe_rows = df[dupes][["Tower ID", "Floor Number"]].drop_duplicates().to_dict("records")
        result.errors.append(f"Building Master: Duplicate floor entries: {dupe_rows}")

    return result


def validate_units(df: pd.DataFrame) -> ValidationResult:
    result = _check_required_columns(df, UNIT_REQUIRED_COLUMNS, "Unit Headcount")
    if not result.is_valid:
        return result

    if (df["Current Total Headcount"] < 0).any():
        result.is_valid = False
        result.errors.append("Unit Headcount: Current Total Headcount cannot be negative.")

    dupes = df.duplicated(subset=["Unit Name"], keep=False)
    if dupes.any():
        result.is_valid = False
        result.errors.append(f"Unit Headcount: Duplicate unit names: {df[dupes]['Unit Name'].unique().tolist()}")

    return result


def validate_attendance(df: pd.DataFrame) -> ValidationResult:
    result = _check_required_columns(df, ATTENDANCE_REQUIRED_COLUMNS, "Attendance")
    if not result.is_valid:
        return result

    if (df["Avg RTO Days/Week"] < 0).any() or (df["Avg RTO Days/Week"] > 7).any():
        result.is_valid = False
        result.errors.append("Attendance: Avg RTO Days/Week must be between 0 and 7.")

    if (df["Monthly Median In-Office Strength"] < 0).any():
        result.is_valid = False
        result.errors.append("Attendance: Monthly Median In-Office Strength cannot be negative.")

    return result


def validate_cross_file(units_df: pd.DataFrame, attendance_df: pd.DataFrame) -> ValidationResult:
    """Check that unit names match across files."""
    result = ValidationResult()
    unit_names = set(units_df["Unit Name"].str.strip())
    attendance_names = set(attendance_df["Unit Name"].str.strip())

    missing_in_attendance = unit_names - attendance_names
    missing_in_units = attendance_names - unit_names

    if missing_in_attendance:
        result.warnings.append(
            f"Units without attendance data: {', '.join(sorted(missing_in_attendance))}. "
            "Default attendance assumptions will be used."
        )
    if missing_in_units:
        result.warnings.append(
            f"Attendance data for unknown units: {', '.join(sorted(missing_in_units))}. "
            "These will be ignored."
        )
    return result
