"""Generate synthetic test datasets for the CPG Seat Planning Platform."""

import pandas as pd
import random
import os


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
        {"Unit Name": "Engineering",  "Current Total Headcount": 400, "HC Growth Forecast (%)": 15, "Attrition Forecast (%)": 8,  "Business Priority": "High"},
        {"Unit Name": "Product",      "Current Total Headcount": 150, "HC Growth Forecast (%)": 10, "Attrition Forecast (%)": 5,  "Business Priority": "High"},
        {"Unit Name": "Sales",        "Current Total Headcount": 300, "HC Growth Forecast (%)": 5,  "Attrition Forecast (%)": 12, "Business Priority": "High"},
        {"Unit Name": "Marketing",    "Current Total Headcount": 120, "HC Growth Forecast (%)": 8,  "Attrition Forecast (%)": 6,  "Business Priority": "High"},
        {"Unit Name": "Finance",      "Current Total Headcount": 80,  "HC Growth Forecast (%)": 2,  "Attrition Forecast (%)": 3,  "Business Priority": "High"},
        {"Unit Name": "HR",           "Current Total Headcount": 60,  "HC Growth Forecast (%)": 3,  "Attrition Forecast (%)": 4,  "Business Priority": "High"},
        {"Unit Name": "Legal",        "Current Total Headcount": 40,  "HC Growth Forecast (%)": 1,  "Attrition Forecast (%)": 2,  "Business Priority": "High"},
        {"Unit Name": "Operations",   "Current Total Headcount": 200, "HC Growth Forecast (%)": -2, "Attrition Forecast (%)": 10, "Business Priority": "High"},
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


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "sample_files")
    generate_sample_csvs(out)
    generate_sample_excel(out)
    print("Sample CSV and Excel files generated in sample_files/")
