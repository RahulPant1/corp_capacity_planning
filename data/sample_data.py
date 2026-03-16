"""Generate synthetic test datasets for the CPG Seat Planning Platform."""

import pandas as pd
import random
import os

# Sample holiday dates within the 90-day window starting 2025-07-01
# (used to validate holiday-skip logic in short-term forecasting)
SAMPLE_HOLIDAY_DATES = [
    "2025-07-04",   # Independence Day
    "2025-09-01",   # Labor Day
    "2025-11-27",   # Thanksgiving
]


def get_sample_holiday_dates() -> list:
    """Return the list of sample holiday date strings."""
    return list(SAMPLE_HOLIDAY_DATES)


def generate_buildings_df() -> pd.DataFrame:
    """Generate building/floor master data: 2 buildings, 2 towers each, 5 floors per tower."""
    random.seed(42)
    rows = []
    buildings = [("B1", "HQ Campus"), ("B2", "Tech Park")]
    for b_id, b_name in buildings:
        for t_idx in range(1, 3):
            tower_id = f"{b_id}-T{t_idx}"
            for floor in range(1, 6):
                rows.append({
                    "Building ID": b_id,
                    "Building Name": b_name,
                    "Tower ID": tower_id,
                    "Floor Number": floor,
                    "Total Seats": random.choice([80, 100, 120, 150]),
                })
    return pd.DataFrame(rows)


def generate_units_df() -> pd.DataFrame:
    """Generate unit headcount & forecast data for 8 business units."""
    profiles = [
        {"Unit Name": "Engineering",  "Current Total Headcount": 400, "HC Growth Forecast (%)": 15, "Business Priority": "High", "Night Shift %": 10},
        {"Unit Name": "Product",      "Current Total Headcount": 150, "HC Growth Forecast (%)": 10, "Business Priority": "High", "Night Shift %": 0},
        {"Unit Name": "Sales",        "Current Total Headcount": 300, "HC Growth Forecast (%)": 5,  "Business Priority": "High", "Night Shift %": 5},
        {"Unit Name": "Marketing",    "Current Total Headcount": 120, "HC Growth Forecast (%)": 8,  "Business Priority": "High", "Night Shift %": 0},
        {"Unit Name": "Finance",      "Current Total Headcount": 80,  "HC Growth Forecast (%)": 2,  "Business Priority": "High", "Night Shift %": 0},
        {"Unit Name": "HR",           "Current Total Headcount": 60,  "HC Growth Forecast (%)": 3,  "Business Priority": "High", "Night Shift %": 0},
        {"Unit Name": "Legal",        "Current Total Headcount": 40,  "HC Growth Forecast (%)": 1,  "Business Priority": "High", "Night Shift %": 0},
        {"Unit Name": "Operations",   "Current Total Headcount": 200, "HC Growth Forecast (%)": -5, "Business Priority": "High", "Night Shift %": 30},
    ]
    return pd.DataFrame(profiles)


def generate_attendance_df() -> pd.DataFrame:
    """Generate attendance & RTO behavior data matching the unit profiles."""
    random.seed(42)
    unit_hcs = {
        "Engineering": 400, "Product": 150, "Sales": 300, "Marketing": 120,
        "Finance": 80, "HR": 60, "Legal": 40, "Operations": 200,
    }
    rows = []
    for unit_name, hc in unit_hcs.items():
        rto = round(random.uniform(2.5, 4.5), 1)
        median_ratio = rto / 5.0 * random.uniform(0.85, 1.0)
        median = round(hc * median_ratio)
        max_hc = round(median * random.uniform(1.1, 1.4))
        rows.append({
            "Unit Name": unit_name,
            "Monthly Median In-Office Strength": median,
            "Monthly Max In-Office Strength": max_hc,
            "Avg RTO Days/Week": rto,
        })
    return pd.DataFrame(rows)


def generate_sample_csvs(output_dir: str):
    """Write sample CSV files to the given directory."""
    os.makedirs(output_dir, exist_ok=True)
    generate_buildings_df().to_csv(os.path.join(output_dir, "buildings.csv"), index=False)
    generate_units_df().to_csv(os.path.join(output_dir, "units.csv"), index=False)
    generate_attendance_df().to_csv(os.path.join(output_dir, "attendance.csv"), index=False)


def generate_sample_excel(output_dir: str):
    """Write a single multi-tab Excel file with all three datasets."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "sample_data.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        generate_buildings_df().to_excel(writer, sheet_name="Buildings", index=False)
        generate_units_df().to_excel(writer, sheet_name="Units", index=False)
        generate_attendance_df().to_excel(writer, sheet_name="Attendance", index=False)


def generate_daily_attendance_df(days: int = 90, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic daily attendance data for all 8 sample units.

    Simulates realistic patterns:
    - Day-of-week effects (Tue/Wed peak, Mon/Fri low)
    - Random noise
    - Slight upward/downward trends per unit
    """
    import numpy as np
    rng = np.random.RandomState(seed)

    # Derive daily base counts from attendance profile medians for numerical consistency.
    # This ensures daily distribution anchors to the same numbers used in Scenario / Unit views.
    _att_df = generate_attendance_df()
    unit_base = dict(zip(_att_df["Unit Name"], _att_df["Monthly Median In-Office Strength"]))

    dow_multipliers = {
        0: 0.85,  # Monday
        1: 1.05,  # Tuesday
        2: 1.10,  # Wednesday
        3: 1.00,  # Thursday
        4: 0.75,  # Friday
    }

    start = pd.Timestamp("2025-07-01")
    dates = pd.bdate_range(start, periods=days)  # Business days only

    rows = []
    for unit, base in unit_base.items():
        trend_slope = rng.uniform(-0.3, 0.5)  # daily trend
        for i, date in enumerate(dates):
            dow = date.dayofweek
            multiplier = dow_multipliers.get(dow, 1.0)
            noise = rng.normal(0, base * 0.08)
            count = max(0, round(base * multiplier + trend_slope * i + noise))
            rows.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Unit Name": unit,
                "In-Office Count": count,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "sample_files")
    generate_sample_csvs(out)
    generate_sample_excel(out)
    print("Sample CSV and Excel files generated in sample_files/")
