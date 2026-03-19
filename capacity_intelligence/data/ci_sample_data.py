"""Sample data generator for the Capacity Intelligence limited version.

Produces:
- TOWERS_META: list of tower dicts (27 towers across 3 cities / 9 buildings)
- BUILDINGS_META: derived list of building-level dicts (backward-compat)
- generate_daily_footfall(): ~9,855-row DataFrame (date × tower, 365 days)

Schema returned by generate_daily_footfall():
    date, tower_id, tower_name, building_id, building_name,
    city, lob, floor_count, footfall, capacity, utilization_pct

Required columns for CSV upload:
    date, building_id, building_name, city, lob, footfall, capacity

Optional columns (present in sample data, absent = graceful degradation):
    tower_id, tower_name, floor_count
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Required / optional column sets (used by Admin tab for upload validation)
# ---------------------------------------------------------------------------
REQUIRED_COLS = {"date", "building_id", "building_name", "city", "lob", "footfall", "capacity"}
OPTIONAL_COLS = {"tower_id", "tower_name", "floor_count"}

# ---------------------------------------------------------------------------
# Tower definitions
# Hierarchy: City → Building (3/city) → Tower (2–3/building) → 10 floors each
# 27 towers total → 27 × 365 = 9,855 rows
# ---------------------------------------------------------------------------
TOWERS_META = [
    # ── Bangalore ──────────────────────────────────────────────────────────
    # Building 1: Prestige Tech Park (Engineering, 3 towers, total 600 seats)
    {
        "tower_id": "BLR-1-TA", "tower_name": "Tower A",
        "building_id": "BLR-1", "building_name": "Prestige Tech Park",
        "city": "Bangalore", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 200, "base_util": 0.84, "growth_rate": 0.16,
    },
    {
        "tower_id": "BLR-1-TB", "tower_name": "Tower B",
        "building_id": "BLR-1", "building_name": "Prestige Tech Park",
        "city": "Bangalore", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 200, "base_util": 0.80, "growth_rate": 0.14,
    },
    {
        "tower_id": "BLR-1-TC", "tower_name": "Tower C",
        "building_id": "BLR-1", "building_name": "Prestige Tech Park",
        "city": "Bangalore", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 200, "base_util": 0.82, "growth_rate": 0.15,
    },
    # Building 2: RMZ Infinity (Product, 2 towers, total 300 seats)
    {
        "tower_id": "BLR-2-TA", "tower_name": "Tower A",
        "building_id": "BLR-2", "building_name": "RMZ Infinity",
        "city": "Bangalore", "lob": "Product",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.76, "growth_rate": 0.10,
    },
    {
        "tower_id": "BLR-2-TB", "tower_name": "Tower B",
        "building_id": "BLR-2", "building_name": "RMZ Infinity",
        "city": "Bangalore", "lob": "Product",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.74, "growth_rate": 0.10,
    },
    # Building 3: Embassy Tech Village (Operations, 2 towers, total 280 seats)
    {
        "tower_id": "BLR-3-TA", "tower_name": "Tower A",
        "building_id": "BLR-3", "building_name": "Embassy Tech Village",
        "city": "Bangalore", "lob": "Operations",
        "floor_count": 10, "total_capacity": 140, "base_util": 0.62, "growth_rate": 0.06,
    },
    {
        "tower_id": "BLR-3-TB", "tower_name": "Tower B",
        "building_id": "BLR-3", "building_name": "Embassy Tech Village",
        "city": "Bangalore", "lob": "Operations",
        "floor_count": 10, "total_capacity": 140, "base_util": 0.60, "growth_rate": 0.05,
    },
    # ── Hyderabad ──────────────────────────────────────────────────────────
    # Building 4: Mindspace Hyderabad (Engineering, 3 towers, total 450 seats)
    {
        "tower_id": "HYD-1-TA", "tower_name": "Tower A",
        "building_id": "HYD-1", "building_name": "Mindspace Hyderabad",
        "city": "Hyderabad", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.72, "growth_rate": 0.08,
    },
    {
        "tower_id": "HYD-1-TB", "tower_name": "Tower B",
        "building_id": "HYD-1", "building_name": "Mindspace Hyderabad",
        "city": "Hyderabad", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.70, "growth_rate": 0.09,
    },
    {
        "tower_id": "HYD-1-TC", "tower_name": "Tower C",
        "building_id": "HYD-1", "building_name": "Mindspace Hyderabad",
        "city": "Hyderabad", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.68, "growth_rate": 0.07,
    },
    # Building 5: DivyaSree (Sales, 2 towers, total 300 seats)
    {
        "tower_id": "HYD-2-TA", "tower_name": "Tower A",
        "building_id": "HYD-2", "building_name": "DivyaSree",
        "city": "Hyderabad", "lob": "Sales",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.71, "growth_rate": 0.05,
    },
    {
        "tower_id": "HYD-2-TB", "tower_name": "Tower B",
        "building_id": "HYD-2", "building_name": "DivyaSree",
        "city": "Hyderabad", "lob": "Sales",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.68, "growth_rate": 0.05,
    },
    # Building 6: Raheja Mindspace (Finance, 2 towers, total 240 seats)
    {
        "tower_id": "HYD-3-TA", "tower_name": "Tower A",
        "building_id": "HYD-3", "building_name": "Raheja Mindspace",
        "city": "Hyderabad", "lob": "Finance",
        "floor_count": 10, "total_capacity": 120, "base_util": 0.55, "growth_rate": 0.02,
    },
    {
        "tower_id": "HYD-3-TB", "tower_name": "Tower B",
        "building_id": "HYD-3", "building_name": "Raheja Mindspace",
        "city": "Hyderabad", "lob": "Finance",
        "floor_count": 10, "total_capacity": 120, "base_util": 0.57, "growth_rate": 0.02,
    },
    # ── Chennai ────────────────────────────────────────────────────────────
    # Building 7: RMZ Millenia (Engineering, 2 towers, total 340 seats)
    {
        "tower_id": "CHN-1-TA", "tower_name": "Tower A",
        "building_id": "CHN-1", "building_name": "RMZ Millenia",
        "city": "Chennai", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 170, "base_util": 0.66, "growth_rate": 0.08,
    },
    {
        "tower_id": "CHN-1-TB", "tower_name": "Tower B",
        "building_id": "CHN-1", "building_name": "RMZ Millenia",
        "city": "Chennai", "lob": "Engineering",
        "floor_count": 10, "total_capacity": 170, "base_util": 0.64, "growth_rate": 0.08,
    },
    # Building 8: Chennai One (Sales, 2 towers, total 260 seats)
    {
        "tower_id": "CHN-2-TA", "tower_name": "Tower A",
        "building_id": "CHN-2", "building_name": "Chennai One",
        "city": "Chennai", "lob": "Sales",
        "floor_count": 10, "total_capacity": 130, "base_util": 0.58, "growth_rate": 0.04,
    },
    {
        "tower_id": "CHN-2-TB", "tower_name": "Tower B",
        "building_id": "CHN-2", "building_name": "Chennai One",
        "city": "Chennai", "lob": "Sales",
        "floor_count": 10, "total_capacity": 130, "base_util": 0.60, "growth_rate": 0.04,
    },
    # Building 9: TIDEL Park (Operations, 3 towers, total 450 seats)
    {
        "tower_id": "CHN-3-TA", "tower_name": "Tower A",
        "building_id": "CHN-3", "building_name": "TIDEL Park",
        "city": "Chennai", "lob": "Operations",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.88, "growth_rate": -0.04,
    },
    {
        "tower_id": "CHN-3-TB", "tower_name": "Tower B",
        "building_id": "CHN-3", "building_name": "TIDEL Park",
        "city": "Chennai", "lob": "Operations",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.90, "growth_rate": -0.05,
    },
    {
        "tower_id": "CHN-3-TC", "tower_name": "Tower C",
        "building_id": "CHN-3", "building_name": "TIDEL Park",
        "city": "Chennai", "lob": "Operations",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.86, "growth_rate": -0.03,
    },
    # ── Manila ─────────────────────────────────────────────────────────────
    # Building 10: BGC One (Technology, 3 towers, total 450 seats)
    {
        "tower_id": "MNL-1-TA", "tower_name": "Tower A",
        "building_id": "MNL-1", "building_name": "BGC One",
        "city": "Manila", "lob": "Technology",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.78, "growth_rate": 0.07,
    },
    {
        "tower_id": "MNL-1-TB", "tower_name": "Tower B",
        "building_id": "MNL-1", "building_name": "BGC One",
        "city": "Manila", "lob": "Technology",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.80, "growth_rate": 0.06,
    },
    {
        "tower_id": "MNL-1-TC", "tower_name": "Tower C",
        "building_id": "MNL-1", "building_name": "BGC One",
        "city": "Manila", "lob": "Technology",
        "floor_count": 10, "total_capacity": 150, "base_util": 0.76, "growth_rate": 0.08,
    },
    # Building 11: Rockwell Business Center (Finance, 2 towers, total 280 seats)
    {
        "tower_id": "MNL-2-TA", "tower_name": "Tower A",
        "building_id": "MNL-2", "building_name": "Rockwell Business Center",
        "city": "Manila", "lob": "Finance",
        "floor_count": 10, "total_capacity": 140, "base_util": 0.65, "growth_rate": 0.03,
    },
    {
        "tower_id": "MNL-2-TB", "tower_name": "Tower B",
        "building_id": "MNL-2", "building_name": "Rockwell Business Center",
        "city": "Manila", "lob": "Finance",
        "floor_count": 10, "total_capacity": 140, "base_util": 0.62, "growth_rate": 0.03,
    },
    # Building 12: Eastwood City Hub (Operations, 2 towers, total 320 seats)
    {
        "tower_id": "MNL-3-TA", "tower_name": "Tower A",
        "building_id": "MNL-3", "building_name": "Eastwood City Hub",
        "city": "Manila", "lob": "Operations",
        "floor_count": 10, "total_capacity": 160, "base_util": 0.85, "growth_rate": -0.04,
    },
    {
        "tower_id": "MNL-3-TB", "tower_name": "Tower B",
        "building_id": "MNL-3", "building_name": "Eastwood City Hub",
        "city": "Manila", "lob": "Operations",
        "floor_count": 10, "total_capacity": 160, "base_util": 0.83, "growth_rate": -0.04,
    },
]

# ---------------------------------------------------------------------------
# Derived BUILDINGS_META — backward-compatible building-level summary
# (deduped from TOWERS_META; capacity = sum of tower capacities per building)
# ---------------------------------------------------------------------------
def _build_buildings_meta() -> list:
    seen = {}
    for t in TOWERS_META:
        bid = t["building_id"]
        if bid not in seen:
            seen[bid] = {
                "building_id": bid,
                "building_name": t["building_name"],
                "city": t["city"],
                "lob": t["lob"],
                "total_capacity": 0,
            }
        seen[bid]["total_capacity"] += t["total_capacity"]
    return list(seen.values())


BUILDINGS_META = _build_buildings_meta()


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
    """Generate a synthetic daily footfall DataFrame for all towers.

    Returns columns:
        date, tower_id, tower_name, building_id, building_name,
        city, lob, floor_count, footfall, capacity, utilization_pct

    Row count: len(TOWERS_META) × horizon_days  (~9,855 rows at defaults)
    """
    rng = np.random.default_rng(seed)
    start = date.today()
    rows = []

    for tower in TOWERS_META:
        cap = tower["total_capacity"]
        base_demand = tower["base_util"] * cap
        annual_growth = tower["growth_rate"]

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
                    "tower_id": tower["tower_id"],
                    "tower_name": tower["tower_name"],
                    "building_id": tower["building_id"],
                    "building_name": tower["building_name"],
                    "city": tower["city"],
                    "lob": tower["lob"],
                    "floor_count": tower["floor_count"],
                    "footfall": footfall,
                    "capacity": cap,
                }
            )

    df = pd.DataFrame(rows)
    df["utilization_pct"] = (df["footfall"] / df["capacity"]).clip(upper=1.30)
    return df


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_buildings_meta() -> list:
    """Return building-level metadata list (backward-compat)."""
    return BUILDINGS_META


def get_towers_meta() -> list:
    """Return full tower-level metadata list."""
    return TOWERS_META


def get_capacity_map() -> dict:
    """Return {building_id: total_capacity} from BUILDINGS_META."""
    return {b["building_id"]: b["total_capacity"] for b in BUILDINGS_META}


def get_tower_map() -> dict:
    """Return {tower_id: tower_name}."""
    return {t["tower_id"]: t["tower_name"] for t in TOWERS_META}


def get_unique_values(field: str) -> list:
    """Return sorted unique values of a field from BUILDINGS_META."""
    return sorted({b[field] for b in BUILDINGS_META if field in b})
