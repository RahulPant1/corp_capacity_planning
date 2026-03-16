"""Sample data generator for the Capacity Intelligence limited version.

Produces:
- BUILDINGS_META: list of building dicts with city / country / LoB / capacity
- generate_daily_footfall(): 365-day forecast DataFrame (date, building, footfall, capacity, …)
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Building definitions
# ---------------------------------------------------------------------------
BUILDINGS_META = [
    {
        "building_id": "BLR-ENG",
        "building_name": "Bangalore Engineering Hub",
        "city": "Bangalore",
        "country": "India",
        "lob": "Engineering",
        "total_capacity": 500,
        "base_util": 0.82,
        "growth_rate": 0.15,   # 15% annual – will breach capacity
    },
    {
        "building_id": "BLR-PROD",
        "building_name": "Bangalore Product Center",
        "city": "Bangalore",
        "country": "India",
        "lob": "Product",
        "total_capacity": 300,
        "base_util": 0.75,
        "growth_rate": 0.10,
    },
    {
        "building_id": "HYD-SALES",
        "building_name": "Hyderabad Sales Tower",
        "city": "Hyderabad",
        "country": "India",
        "lob": "Sales",
        "total_capacity": 400,
        "base_util": 0.70,
        "growth_rate": 0.05,
    },
    {
        "building_id": "HYD-FIN",
        "building_name": "Hyderabad Finance Office",
        "city": "Hyderabad",
        "country": "India",
        "lob": "Finance",
        "total_capacity": 250,
        "base_util": 0.55,
        "growth_rate": 0.02,   # low utilisation
    },
    {
        "building_id": "CHN-ENG",
        "building_name": "Chennai Engineering Annex",
        "city": "Chennai",
        "country": "India",
        "lob": "Engineering",
        "total_capacity": 350,
        "base_util": 0.65,
        "growth_rate": 0.08,
    },
    {
        "building_id": "MNL-OPS",
        "building_name": "Manila Operations Hub",
        "city": "Manila",
        "country": "Philippines",
        "lob": "Operations",
        "total_capacity": 450,
        "base_util": 0.88,
        "growth_rate": -0.05,  # shrinking but still near capacity
    },
    {
        "building_id": "MNL-SALES",
        "building_name": "Manila Sales Office",
        "city": "Manila",
        "country": "Philippines",
        "lob": "Sales",
        "total_capacity": 200,
        "base_util": 0.50,
        "growth_rate": 0.03,
    },
]

# Day-of-week footfall multipliers (0=Monday … 6=Sunday)
DOW_MULTIPLIERS = {
    0: 0.85,  # Monday
    1: 1.00,  # Tuesday
    2: 1.00,  # Wednesday
    3: 0.95,  # Thursday
    4: 0.75,  # Friday
    5: 0.05,  # Saturday
    6: 0.02,  # Sunday
}


def generate_daily_footfall(seed: int = 42, horizon_days: int = 365) -> pd.DataFrame:
    """Generate a synthetic daily footfall DataFrame for all buildings.

    Returns columns:
        date, building_id, building_name, city, country, lob,
        footfall, capacity, utilization_pct
    """
    rng = np.random.default_rng(seed)
    start = date.today()
    rows = []

    for bldg in BUILDINGS_META:
        cap = bldg["total_capacity"]
        base_demand = bldg["base_util"] * cap
        annual_growth = bldg["growth_rate"]

        for i in range(horizon_days):
            d = start + timedelta(days=i)
            dow_mult = DOW_MULTIPLIERS[d.weekday()]
            trend_factor = 1.0 + annual_growth * (i / 365.0)
            expected = base_demand * dow_mult * trend_factor
            noise_factor = 1.0 + rng.normal(0, 0.08)
            footfall = int(max(0, round(expected * noise_factor)))

            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "building_id": bldg["building_id"],
                    "building_name": bldg["building_name"],
                    "city": bldg["city"],
                    "country": bldg["country"],
                    "lob": bldg["lob"],
                    "footfall": footfall,
                    "capacity": cap,
                }
            )

    df = pd.DataFrame(rows)
    df["utilization_pct"] = (df["footfall"] / df["capacity"]).clip(upper=1.30)
    return df


def get_buildings_meta() -> list:
    return BUILDINGS_META


def get_capacity_map() -> dict:
    return {b["building_id"]: b["total_capacity"] for b in BUILDINGS_META}


def get_unique_values(field: str) -> list:
    return sorted({b[field] for b in BUILDINGS_META})
