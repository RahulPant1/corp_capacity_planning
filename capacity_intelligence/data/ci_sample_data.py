"""Sample data generator for the Capacity Intelligence app — 4-dataset model.

Generates:
  DS1 — Floor Capacity:    City, Building Name, Floor, Total Capacity
  DS2 — Seat Allocation:   LOB, LOB Leader Name, City, Building Name, Floor, Allocated Seats
  DS3 — Total Headcount:   LOB, Leader, Headcount
  DS4 — 60-Day Prediction: Date, Day, City, Building Name, Floor, LOB, Leader,
                            Holiday Flag, Optional Holiday Flag, Optional Holiday Name,
                            US Holiday Flag, Employee Count Predicted

Join keys:
  (City, Building Name, Floor)       — links DS1, DS2, DS4
  LOB                                — links DS2, DS3, DS4

Column name constants:
  Defined here as COL_* and mirrored in engine/capacity_forecast.py as C_*.
  Both sets refer to the same physical column names. If you rename a column,
  update BOTH files. See CLAUDE.md → "Column name constants" for the full list.
"""

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Column name constants (single source of truth for joins)
# ---------------------------------------------------------------------------
COL_CITY          = "City"
COL_BUILDING      = "Building Name"
COL_FLOOR         = "Floor"
COL_LOB           = "LOB"
COL_LEADER        = "Leader"
COL_LOB_LEADER    = "LOB Leader Name"
COL_TOTAL_CAP     = "Total Capacity"
COL_ALLOC_SEATS   = "Allocated Seats"
COL_HEADCOUNT     = "Headcount"
COL_DATE          = "Date"
COL_DAY           = "Day"
COL_HOL           = "Holiday Flag"
COL_OPT_HOL       = "Optional Holiday Flag"
COL_OPT_HOL_NAME  = "Optional Holiday Name"
COL_US_HOL        = "US Holiday Flag"
COL_PREDICTED     = "Employee Count Predicted"

# Derived columns (added by build_daily_df)
COL_UTIL_PCT      = "Utilization Pct"
COL_SEAT_GAP      = "Seat Gap"          # Allocated Seats − Predicted
COL_HC_GAP        = "HC Gap"            # Allocated Seats − Headcount (static)

FLOOR_CAPACITY_COLS  = [COL_CITY, COL_BUILDING, COL_FLOOR, COL_TOTAL_CAP]
SEAT_ALLOC_COLS      = [COL_LOB, COL_LOB_LEADER, COL_CITY, COL_BUILDING, COL_FLOOR, COL_ALLOC_SEATS]
HEADCOUNT_COLS       = [COL_LOB, COL_LEADER, COL_HEADCOUNT]
PREDICTION_COLS      = [
    COL_DATE, COL_DAY, COL_CITY, COL_BUILDING, COL_FLOOR,
    COL_LOB, COL_LEADER,
    COL_HOL, COL_OPT_HOL, COL_OPT_HOL_NAME, COL_US_HOL,
    COL_PREDICTED,
]

# ---------------------------------------------------------------------------
# DS1 — Floor Capacity
# ---------------------------------------------------------------------------
_FLOOR_CAPACITY_ROWS = [
    # Bangalore — Prestige Tech Park
    {COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park",       COL_FLOOR: 3,  COL_TOTAL_CAP: 120},
    {COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park",       COL_FLOOR: 4,  COL_TOTAL_CAP: 120},
    {COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park",       COL_FLOOR: 5,  COL_TOTAL_CAP: 100},
    # Bangalore — RMZ Infinity
    {COL_CITY: "Bangalore", COL_BUILDING: "RMZ Infinity",             COL_FLOOR: 2,  COL_TOTAL_CAP: 100},
    {COL_CITY: "Bangalore", COL_BUILDING: "RMZ Infinity",             COL_FLOOR: 3,  COL_TOTAL_CAP: 100},
    # Bangalore — Embassy Tech Village
    {COL_CITY: "Bangalore", COL_BUILDING: "Embassy Tech Village",     COL_FLOOR: 1,  COL_TOTAL_CAP:  90},
    {COL_CITY: "Bangalore", COL_BUILDING: "Embassy Tech Village",     COL_FLOOR: 2,  COL_TOTAL_CAP:  90},
    # Hyderabad — Mindspace Hyderabad
    {COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad",      COL_FLOOR: 4,  COL_TOTAL_CAP: 130},
    {COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad",      COL_FLOOR: 5,  COL_TOTAL_CAP: 130},
    {COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad",      COL_FLOOR: 6,  COL_TOTAL_CAP: 110},
    # Hyderabad — DivyaSree
    {COL_CITY: "Hyderabad", COL_BUILDING: "DivyaSree",                COL_FLOOR: 2,  COL_TOTAL_CAP: 100},
    {COL_CITY: "Hyderabad", COL_BUILDING: "DivyaSree",                COL_FLOOR: 3,  COL_TOTAL_CAP: 100},
    # Hyderabad — Raheja Mindspace
    {COL_CITY: "Hyderabad", COL_BUILDING: "Raheja Mindspace",         COL_FLOOR: 1,  COL_TOTAL_CAP:  80},
    {COL_CITY: "Hyderabad", COL_BUILDING: "Raheja Mindspace",         COL_FLOOR: 2,  COL_TOTAL_CAP:  80},
    # Chennai — RMZ Millenia
    {COL_CITY: "Chennai",   COL_BUILDING: "RMZ Millenia",             COL_FLOOR: 3,  COL_TOTAL_CAP: 110},
    {COL_CITY: "Chennai",   COL_BUILDING: "RMZ Millenia",             COL_FLOOR: 4,  COL_TOTAL_CAP: 110},
    # Chennai — Chennai One
    {COL_CITY: "Chennai",   COL_BUILDING: "Chennai One",              COL_FLOOR: 2,  COL_TOTAL_CAP:  90},
    {COL_CITY: "Chennai",   COL_BUILDING: "Chennai One",              COL_FLOOR: 3,  COL_TOTAL_CAP:  90},
    # Chennai — TIDEL Park
    {COL_CITY: "Chennai",   COL_BUILDING: "TIDEL Park",               COL_FLOOR: 5,  COL_TOTAL_CAP: 120},
    {COL_CITY: "Chennai",   COL_BUILDING: "TIDEL Park",               COL_FLOOR: 6,  COL_TOTAL_CAP: 120},
    {COL_CITY: "Chennai",   COL_BUILDING: "TIDEL Park",               COL_FLOOR: 7,  COL_TOTAL_CAP: 100},
    # Manila — BGC One
    {COL_CITY: "Manila",    COL_BUILDING: "BGC One",                  COL_FLOOR: 8,  COL_TOTAL_CAP: 130},
    {COL_CITY: "Manila",    COL_BUILDING: "BGC One",                  COL_FLOOR: 9,  COL_TOTAL_CAP: 130},
    {COL_CITY: "Manila",    COL_BUILDING: "BGC One",                  COL_FLOOR: 10, COL_TOTAL_CAP: 110},
    # Manila — Rockwell Business Center
    {COL_CITY: "Manila",    COL_BUILDING: "Rockwell Business Center", COL_FLOOR: 3,  COL_TOTAL_CAP: 100},
    {COL_CITY: "Manila",    COL_BUILDING: "Rockwell Business Center", COL_FLOOR: 4,  COL_TOTAL_CAP: 100},
    # Manila — Eastwood City Hub
    {COL_CITY: "Manila",    COL_BUILDING: "Eastwood City Hub",        COL_FLOOR: 2,  COL_TOTAL_CAP: 110},
    {COL_CITY: "Manila",    COL_BUILDING: "Eastwood City Hub",        COL_FLOOR: 3,  COL_TOTAL_CAP: 110},
]

# ---------------------------------------------------------------------------
# DS2 — Seat Allocation (multiple LOBs per floor)
# Rule: sum(Allocated Seats per floor) ≤ Total Capacity
# ---------------------------------------------------------------------------
_SEAT_ALLOCATION_ROWS = [
    # ── Prestige Tech Park ────────────────────────────────────────────────
    # Floor 3 (cap 120): Engineering 70 + Product 40 = 110
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park", COL_FLOOR: 3, COL_ALLOC_SEATS: 70},
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park", COL_FLOOR: 3, COL_ALLOC_SEATS: 40},
    # Floor 4 (cap 120): Engineering 60 + Operations 50 = 110
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park", COL_FLOOR: 4, COL_ALLOC_SEATS: 60},
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park", COL_FLOOR: 4, COL_ALLOC_SEATS: 50},
    # Floor 5 (cap 100): Product 50 + HR 40 = 90
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park", COL_FLOOR: 5, COL_ALLOC_SEATS: 50},
    {COL_LOB: "HR",          COL_LOB_LEADER: "Deepa Nair",    COL_CITY: "Bangalore", COL_BUILDING: "Prestige Tech Park", COL_FLOOR: 5, COL_ALLOC_SEATS: 40},
    # ── RMZ Infinity ─────────────────────────────────────────────────────
    # Floor 2 (cap 100): Product 55 + Sales 35 = 90
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Bangalore", COL_BUILDING: "RMZ Infinity", COL_FLOOR: 2, COL_ALLOC_SEATS: 55},
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Bangalore", COL_BUILDING: "RMZ Infinity", COL_FLOOR: 2, COL_ALLOC_SEATS: 35},
    # Floor 3 (cap 100): Product 45 + Engineering 40 = 85
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Bangalore", COL_BUILDING: "RMZ Infinity", COL_FLOOR: 3, COL_ALLOC_SEATS: 45},
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Bangalore", COL_BUILDING: "RMZ Infinity", COL_FLOOR: 3, COL_ALLOC_SEATS: 40},
    # ── Embassy Tech Village ──────────────────────────────────────────────
    # Floor 1 (cap 90): Operations 50 + Finance 30 = 80
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Bangalore", COL_BUILDING: "Embassy Tech Village", COL_FLOOR: 1, COL_ALLOC_SEATS: 50},
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Bangalore", COL_BUILDING: "Embassy Tech Village", COL_FLOOR: 1, COL_ALLOC_SEATS: 30},
    # Floor 2 (cap 90): Operations 55 + HR 25 = 80
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Bangalore", COL_BUILDING: "Embassy Tech Village", COL_FLOOR: 2, COL_ALLOC_SEATS: 55},
    {COL_LOB: "HR",          COL_LOB_LEADER: "Deepa Nair",    COL_CITY: "Bangalore", COL_BUILDING: "Embassy Tech Village", COL_FLOOR: 2, COL_ALLOC_SEATS: 25},
    # ── Mindspace Hyderabad ───────────────────────────────────────────────
    # Floor 4 (cap 130): Engineering 75 + Technology 45 = 120
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad", COL_FLOOR: 4, COL_ALLOC_SEATS: 75},
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad", COL_FLOOR: 4, COL_ALLOC_SEATS: 45},
    # Floor 5 (cap 130): Engineering 65 + Product 50 = 115
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad", COL_FLOOR: 5, COL_ALLOC_SEATS: 65},
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad", COL_FLOOR: 5, COL_ALLOC_SEATS: 50},
    # Floor 6 (cap 110): Sales 55 + Finance 40 = 95
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad", COL_FLOOR: 6, COL_ALLOC_SEATS: 55},
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Hyderabad", COL_BUILDING: "Mindspace Hyderabad", COL_FLOOR: 6, COL_ALLOC_SEATS: 40},
    # ── DivyaSree ─────────────────────────────────────────────────────────
    # Floor 2 (cap 100): Sales 55 + Operations 35 = 90
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Hyderabad", COL_BUILDING: "DivyaSree", COL_FLOOR: 2, COL_ALLOC_SEATS: 55},
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Hyderabad", COL_BUILDING: "DivyaSree", COL_FLOOR: 2, COL_ALLOC_SEATS: 35},
    # Floor 3 (cap 100): Sales 45 + Technology 40 = 85
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Hyderabad", COL_BUILDING: "DivyaSree", COL_FLOOR: 3, COL_ALLOC_SEATS: 45},
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Hyderabad", COL_BUILDING: "DivyaSree", COL_FLOOR: 3, COL_ALLOC_SEATS: 40},
    # ── Raheja Mindspace ──────────────────────────────────────────────────
    # Floor 1 (cap 80): Finance 45 + HR 25 = 70
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Hyderabad", COL_BUILDING: "Raheja Mindspace", COL_FLOOR: 1, COL_ALLOC_SEATS: 45},
    {COL_LOB: "HR",          COL_LOB_LEADER: "Deepa Nair",    COL_CITY: "Hyderabad", COL_BUILDING: "Raheja Mindspace", COL_FLOOR: 1, COL_ALLOC_SEATS: 25},
    # Floor 2 (cap 80): Finance 40 + Operations 30 = 70
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Hyderabad", COL_BUILDING: "Raheja Mindspace", COL_FLOOR: 2, COL_ALLOC_SEATS: 40},
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Hyderabad", COL_BUILDING: "Raheja Mindspace", COL_FLOOR: 2, COL_ALLOC_SEATS: 30},
    # ── RMZ Millenia ─────────────────────────────────────────────────────
    # Floor 3 (cap 110): Engineering 60 + Technology 40 = 100
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Chennai", COL_BUILDING: "RMZ Millenia", COL_FLOOR: 3, COL_ALLOC_SEATS: 60},
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Chennai", COL_BUILDING: "RMZ Millenia", COL_FLOOR: 3, COL_ALLOC_SEATS: 40},
    # Floor 4 (cap 110): Engineering 55 + Product 45 = 100
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Chennai", COL_BUILDING: "RMZ Millenia", COL_FLOOR: 4, COL_ALLOC_SEATS: 55},
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Chennai", COL_BUILDING: "RMZ Millenia", COL_FLOOR: 4, COL_ALLOC_SEATS: 45},
    # ── Chennai One ──────────────────────────────────────────────────────
    # Floor 2 (cap 90): Sales 50 + Operations 30 = 80
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Chennai", COL_BUILDING: "Chennai One", COL_FLOOR: 2, COL_ALLOC_SEATS: 50},
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Chennai", COL_BUILDING: "Chennai One", COL_FLOOR: 2, COL_ALLOC_SEATS: 30},
    # Floor 3 (cap 90): Sales 40 + HR 35 = 75
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Chennai", COL_BUILDING: "Chennai One", COL_FLOOR: 3, COL_ALLOC_SEATS: 40},
    {COL_LOB: "HR",          COL_LOB_LEADER: "Deepa Nair",    COL_CITY: "Chennai", COL_BUILDING: "Chennai One", COL_FLOOR: 3, COL_ALLOC_SEATS: 35},
    # ── TIDEL Park ───────────────────────────────────────────────────────
    # Floor 5 (cap 120): Operations 70 + Finance 40 = 110
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Chennai", COL_BUILDING: "TIDEL Park", COL_FLOOR: 5, COL_ALLOC_SEATS: 70},
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Chennai", COL_BUILDING: "TIDEL Park", COL_FLOOR: 5, COL_ALLOC_SEATS: 40},
    # Floor 6 (cap 120): Operations 65 + Engineering 45 = 110
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Chennai", COL_BUILDING: "TIDEL Park", COL_FLOOR: 6, COL_ALLOC_SEATS: 65},
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Chennai", COL_BUILDING: "TIDEL Park", COL_FLOOR: 6, COL_ALLOC_SEATS: 45},
    # Floor 7 (cap 100): Operations 55 + Technology 35 = 90
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Chennai", COL_BUILDING: "TIDEL Park", COL_FLOOR: 7, COL_ALLOC_SEATS: 55},
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Chennai", COL_BUILDING: "TIDEL Park", COL_FLOOR: 7, COL_ALLOC_SEATS: 35},
    # ── BGC One ──────────────────────────────────────────────────────────
    # Floor 8 (cap 130): Technology 75 + Engineering 45 = 120
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Manila", COL_BUILDING: "BGC One", COL_FLOOR: 8,  COL_ALLOC_SEATS: 75},
    {COL_LOB: "Engineering", COL_LOB_LEADER: "Priya Sharma",  COL_CITY: "Manila", COL_BUILDING: "BGC One", COL_FLOOR: 8,  COL_ALLOC_SEATS: 45},
    # Floor 9 (cap 130): Technology 65 + Product 50 = 115
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Manila", COL_BUILDING: "BGC One", COL_FLOOR: 9,  COL_ALLOC_SEATS: 65},
    {COL_LOB: "Product",     COL_LOB_LEADER: "Kiran Mehta",   COL_CITY: "Manila", COL_BUILDING: "BGC One", COL_FLOOR: 9,  COL_ALLOC_SEATS: 50},
    # Floor 10 (cap 110): Technology 55 + Finance 40 = 95
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Manila", COL_BUILDING: "BGC One", COL_FLOOR: 10, COL_ALLOC_SEATS: 55},
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Manila", COL_BUILDING: "BGC One", COL_FLOOR: 10, COL_ALLOC_SEATS: 40},
    # ── Rockwell Business Center ─────────────────────────────────────────
    # Floor 3 (cap 100): Finance 55 + HR 35 = 90
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Manila", COL_BUILDING: "Rockwell Business Center", COL_FLOOR: 3, COL_ALLOC_SEATS: 55},
    {COL_LOB: "HR",          COL_LOB_LEADER: "Deepa Nair",    COL_CITY: "Manila", COL_BUILDING: "Rockwell Business Center", COL_FLOOR: 3, COL_ALLOC_SEATS: 35},
    # Floor 4 (cap 100): Finance 50 + Operations 40 = 90
    {COL_LOB: "Finance",     COL_LOB_LEADER: "Vikram Singh",  COL_CITY: "Manila", COL_BUILDING: "Rockwell Business Center", COL_FLOOR: 4, COL_ALLOC_SEATS: 50},
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Manila", COL_BUILDING: "Rockwell Business Center", COL_FLOOR: 4, COL_ALLOC_SEATS: 40},
    # ── Eastwood City Hub ────────────────────────────────────────────────
    # Floor 2 (cap 110): Operations 65 + Technology 35 = 100
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Manila", COL_BUILDING: "Eastwood City Hub", COL_FLOOR: 2, COL_ALLOC_SEATS: 65},
    {COL_LOB: "Technology",  COL_LOB_LEADER: "Maria Santos",  COL_CITY: "Manila", COL_BUILDING: "Eastwood City Hub", COL_FLOOR: 2, COL_ALLOC_SEATS: 35},
    # Floor 3 (cap 110): Operations 60 + Sales 40 = 100
    {COL_LOB: "Operations",  COL_LOB_LEADER: "Suresh Rao",    COL_CITY: "Manila", COL_BUILDING: "Eastwood City Hub", COL_FLOOR: 3, COL_ALLOC_SEATS: 60},
    {COL_LOB: "Sales",       COL_LOB_LEADER: "Anjali Patel",  COL_CITY: "Manila", COL_BUILDING: "Eastwood City Hub", COL_FLOOR: 3, COL_ALLOC_SEATS: 40},
]

# ---------------------------------------------------------------------------
# DS3 — Total Headcount (LOB-level snapshot)
# ---------------------------------------------------------------------------
_HEADCOUNT_ROWS = [
    {COL_LOB: "Engineering", COL_LEADER: "Priya Sharma", COL_HEADCOUNT: 350},
    {COL_LOB: "Product",     COL_LEADER: "Kiran Mehta",  COL_HEADCOUNT: 200},
    {COL_LOB: "Operations",  COL_LEADER: "Suresh Rao",   COL_HEADCOUNT: 300},
    {COL_LOB: "Sales",       COL_LEADER: "Anjali Patel", COL_HEADCOUNT: 180},
    {COL_LOB: "Finance",     COL_LEADER: "Vikram Singh", COL_HEADCOUNT: 150},
    {COL_LOB: "Technology",  COL_LEADER: "Maria Santos", COL_HEADCOUNT: 250},
    {COL_LOB: "HR",          COL_LEADER: "Deepa Nair",   COL_HEADCOUNT:  80},
]

# ---------------------------------------------------------------------------
# DS4 — 60-Day Prediction: generation parameters
# ---------------------------------------------------------------------------

# Base utilization rate per LOB (fraction of allocated seats expected in office on a typical Wed)
# If a new LOB is added to _SEAT_ALLOCATION_ROWS, add its rate here too.
# Missing LOBs silently fall back to 0.70 in get_prediction_df().
_LOB_BASE_UTIL = {
    "Engineering": 0.82,
    "Product":     0.74,
    "Operations":  0.78,
    "Sales":       0.70,
    "Finance":     0.58,
    "Technology":  0.80,
    "HR":          0.62,
}

# Day-of-week attendance multipliers (0=Mon … 6=Sun)
_DOW_MULT = {0: 0.82, 1: 0.95, 2: 1.00, 3: 0.90, 4: 0.70, 5: 0.05, 6: 0.02}
_DOW_NAME  = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
              4: "Friday", 5: "Saturday", 6: "Sunday"}

# Holiday calendar baked into sample prediction data.
# These are specific to the Apr–Jun 2026 window. Refresh annually when updating the sample data.
# Admins can also add/override holidays at runtime via Admin → Holiday Calendar without a code change.
# Format: {offset_days: (holiday_flag, opt_flag, opt_name, us_flag)}
def _build_holiday_map(start: date) -> dict:
    hmap = {}
    for offset in range(60):
        d = start + timedelta(days=offset)
        hol, opt, opt_name, us = 0, 0, "", 0
        if d.month == 5 and d.day == 1:    # International Labour Day
            hol = 1
        if d.month == 5 and d.day == 26:   # Memorial Day (US) — last Mon of May 2026
            us = 1
        if d.month == 6 and d.day == 5:    # World Environment Day (optional)
            opt, opt_name = 1, "World Environment Day"
        if d.month == 6 and d.day == 19:   # Juneteenth (US)
            us = 1
        hmap[offset] = (hol, opt, opt_name, us)
    return hmap


# ---------------------------------------------------------------------------
# Public accessor functions — return clean DataFrames
# ---------------------------------------------------------------------------

def get_floor_capacity_df() -> pd.DataFrame:
    """DS1 — Floor Capacity snapshot."""
    return pd.DataFrame(_FLOOR_CAPACITY_ROWS)[FLOOR_CAPACITY_COLS]


def get_seat_allocation_df() -> pd.DataFrame:
    """DS2 — Seat Allocation snapshot (multiple LOBs per floor)."""
    return pd.DataFrame(_SEAT_ALLOCATION_ROWS)[SEAT_ALLOC_COLS]


def get_headcount_df() -> pd.DataFrame:
    """DS3 — Total Headcount by LOB."""
    return pd.DataFrame(_HEADCOUNT_ROWS)[HEADCOUNT_COLS]


def get_sample_holiday_df() -> pd.DataFrame:
    """Return a structured holiday calendar DataFrame for the sample data window.

    Columns: Date (Timestamp), City, Holiday Type, Holiday Name
    City = "All" means the holiday applies across all cities.
    Holiday Type: "Mandatory", "Optional", or "US"
    Used to pre-populate the Admin → Holiday Calendar table.
    """
    start = date.today()
    hmap = _build_holiday_map(start)
    rows = []
    for offset, (hol, opt, opt_name, us) in hmap.items():
        d = pd.Timestamp(start + timedelta(days=offset))
        if hol:
            rows.append({"Date": d, "City": "All",   "Holiday Type": "Mandatory", "Holiday Name": "International Labour Day"})
        if us:
            name = "Memorial Day (US)" if (d.month == 5) else "Juneteenth (US)"
            rows.append({"Date": d, "City": "All",   "Holiday Type": "US",        "Holiday Name": name})
        if opt and opt_name:
            rows.append({"Date": d, "City": "All",   "Holiday Type": "Optional",  "Holiday Name": opt_name})
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["Date", "City", "Holiday Type", "Holiday Name"]
    )


def get_prediction_df(seed: int = 42, horizon_days: int = 60) -> pd.DataFrame:
    """DS4 — 60-day predicted attendance at (Date × Building × Floor × LOB) granularity.

    Uses seat allocation rows as the universe of (building, floor, lob) combinations.
    Prediction = allocated_seats × lob_base_util × dow_multiplier × noise.
    Row count: len(allocation_rows) × horizon_days  (~3,480 rows at defaults)
    """
    rng = np.random.default_rng(seed)
    start = date.today()
    holiday_map = _build_holiday_map(start)
    rows = []

    for alloc in _SEAT_ALLOCATION_ROWS:
        city    = alloc[COL_CITY]
        building = alloc[COL_BUILDING]
        floor   = alloc[COL_FLOOR]
        lob     = alloc[COL_LOB]
        leader  = alloc[COL_LOB_LEADER]
        alloc_seats = alloc[COL_ALLOC_SEATS]
        base_util   = _LOB_BASE_UTIL.get(lob, 0.70)
        base_demand = alloc_seats * base_util

        for i in range(horizon_days):
            d = start + timedelta(days=i)
            hol, opt, opt_name, us = holiday_map.get(i, (0, 0, "", 0))

            dow_mult = _DOW_MULT[d.weekday()]
            holiday_reduction = 1.0
            if hol:
                holiday_reduction *= 0.10
            elif opt:
                holiday_reduction *= 0.60
            elif us:
                holiday_reduction *= 0.75

            expected = base_demand * dow_mult * holiday_reduction
            noise    = 1.0 + rng.normal(0, 0.07)
            predicted = int(max(0, round(expected * noise)))

            rows.append({
                COL_DATE:         pd.Timestamp(d),
                COL_DAY:          _DOW_NAME[d.weekday()],
                COL_CITY:         city,
                COL_BUILDING:     building,
                COL_FLOOR:        floor,
                COL_LOB:          lob,
                COL_LEADER:       leader,
                COL_HOL:          hol,
                COL_OPT_HOL:      opt,
                COL_OPT_HOL_NAME: opt_name,
                COL_US_HOL:       us,
                COL_PREDICTED:    predicted,
            })

    return pd.DataFrame(rows)[PREDICTION_COLS]


# ---------------------------------------------------------------------------
# Join helper — builds the working daily_df used by all tabs
# ---------------------------------------------------------------------------

def build_daily_df(
    floor_cap_df: pd.DataFrame,
    allocation_df: pd.DataFrame,
    headcount_df: pd.DataFrame,
    prediction_df: pd.DataFrame,
) -> pd.DataFrame:
    """Join all 4 datasets into the working DataFrame consumed by every tab.

    Returned columns (superset of DS4):
        Date, Day, City, Building Name, Floor, LOB, Leader,
        Holiday Flag, Optional Holiday Flag, Optional Holiday Name, US Holiday Flag,
        Employee Count Predicted,
        Total Capacity,       ← from DS1
        Allocated Seats,      ← from DS2
        Headcount,            ← from DS3
        Utilization Pct,      ← Predicted / Total Capacity  (clipped at 1.30)
        Seat Gap,             ← Allocated Seats − Predicted
        HC Gap,               ← Allocated Seats − Headcount (static LOB snapshot)
    """
    floor_key  = [COL_CITY, COL_BUILDING, COL_FLOOR]
    lob_key    = [COL_CITY, COL_BUILDING, COL_FLOOR, COL_LOB]

    # Normalise join keys: strip whitespace, consistent string type
    for df in (floor_cap_df, allocation_df, prediction_df):
        for col in floor_key:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

    alloc_slim = allocation_df[[*lob_key, COL_ALLOC_SEATS]].copy()
    cap_slim   = floor_cap_df[[*floor_key, COL_TOTAL_CAP]].copy()
    hc_slim    = headcount_df[[COL_LOB, COL_HEADCOUNT]].copy()

    df = prediction_df.copy()
    df = df.merge(cap_slim,   on=floor_key, how="left")
    df = df.merge(alloc_slim, on=lob_key,   how="left")
    df = df.merge(hc_slim,    on=COL_LOB,   how="left")

    df[COL_UTIL_PCT] = (df[COL_PREDICTED] / df[COL_TOTAL_CAP]).clip(upper=1.30).round(3)
    df[COL_SEAT_GAP] = df[COL_ALLOC_SEATS] - df[COL_PREDICTED]
    df[COL_HC_GAP]   = df[COL_ALLOC_SEATS] - df[COL_HEADCOUNT]

    return df


# ---------------------------------------------------------------------------
# Buildings metadata — derived from DS1 for backward-compat (scenario planner)
# ---------------------------------------------------------------------------

def get_buildings_meta(floor_cap_df: Optional[pd.DataFrame] = None) -> list:
    """Return building-level summary list for sidebar and scenario planner filters.

    Each entry: {building_id, building_name, city, total_capacity}
    building_id is synthesised as '<CITY_CODE>-<index>' for display purposes.
    """
    df = floor_cap_df if floor_cap_df is not None else get_floor_capacity_df()
    grp = (
        df.groupby([COL_CITY, COL_BUILDING], sort=False)[COL_TOTAL_CAP]
        .sum()
        .reset_index()
    )
    result = []
    city_counters: dict = {}
    city_codes = {"Bangalore": "BLR", "Hyderabad": "HYD", "Chennai": "CHN", "Manila": "MNL"}
    for _, row in grp.iterrows():
        city = row[COL_CITY]
        code = city_codes.get(city, city[:3].upper())
        city_counters[code] = city_counters.get(code, 0) + 1
        result.append({
            "building_id":    f"{code}-{city_counters[code]}",
            "building_name":  row[COL_BUILDING],
            "city":           city,
            "total_capacity": int(row[COL_TOTAL_CAP]),
        })
    return result
