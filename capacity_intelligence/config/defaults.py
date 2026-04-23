"""Default configuration constants for the CPG Seat Planning Platform.

Constants are grouped into two sections:
  ACTIVE   — used by the current Streamlit tabs (capacity_forecast.py, scenario_report.py)
  FOR_FUTURE — reserved for the Seat Allocation tab (for_future/engine/); safe to ignore for now
"""

# ===========================================================================
# ACTIVE — used by current UI tabs
# ===========================================================================

# Working days per week (for RTO ratio calculation)
WORKING_DAYS_PER_WEEK = 5

# Set to True to show the Long-Term View tab once a 6-12 month prediction model is available.
ENABLE_LONG_TERM_VIEW = False

# ---------------------------------------------------------------------------
# Risk tier thresholds — used by capacity_forecast.py and tab_short_term.py
# Values are fractions (0–1), matching the Utilization Pct column in ci_daily_df.
# If you change a threshold here it automatically updates all tables and charts.
# ---------------------------------------------------------------------------
RISK_THRESHOLDS = {
    "over_capacity":  0.90,   # Peak util > 90% → 🔴 Over Capacity
    "watch":          0.75,   # Avg  util > 75% → 🟡 Watch
    "under_utilized": 0.60,   # Avg  util < 60% → 🔵 Under-utilized
    # Anything else           →              🟢 Healthy
}

# ---------------------------------------------------------------------------
# Risk tier display colours — used by tab_short_term.py style functions.
# Keys must match the label strings produced by get_risk_label() below.
# ---------------------------------------------------------------------------
RISK_COLOURS = {
    "🔴 Over Capacity":  "#dc3545",   # red
    "🟡 Watch":          "#856404",   # amber
    "🔵 Under-utilized": "#6c757d",   # grey
    "🟢 Healthy":        "#155724",   # green
}

# Convenience function — call this instead of writing if/elif chains in tabs.
def get_risk_label(peak_util_pct: float, avg_util_pct: float) -> str:
    """Return the risk tier label for a building or floor.

    Args:
        peak_util_pct: peak utilization as a percentage (0–130)
        avg_util_pct:  avg  utilization as a percentage (0–130)
    """
    if peak_util_pct > RISK_THRESHOLDS["over_capacity"]  * 100: return "🔴 Over Capacity"
    if avg_util_pct  > RISK_THRESHOLDS["watch"]          * 100: return "🟡 Watch"
    if avg_util_pct  < RISK_THRESHOLDS["under_utilized"] * 100: return "🔵 Under-utilized"
    return "🟢 Healthy"

# ---------------------------------------------------------------------------
# Scenario Planner — event adjustment multipliers
# Each entry: {event_key: {"label": display_name, "multiplier": float}}
# Multiplier > 1.0 increases footfall; < 1.0 decreases footfall.
# Admins can override these at runtime via the Admin tab.
# ---------------------------------------------------------------------------
DEFAULT_SCENARIO_MULTIPLIERS = {
    "townhall":           {"label": "Townhall",                   "multiplier": 1.20},
    "leadership_visit":   {"label": "Leadership Visit",           "multiplier": 1.15},
    "weather_alert":      {"label": "Weather Alert",              "multiplier": 0.70},
    "traffic_disruption": {"label": "Traffic / Local Disruption", "multiplier": 0.80},
    "mandatory_holiday":  {"label": "Mandatory Holiday",          "multiplier": 0.10},
    "optional_holiday":   {"label": "Optional Holiday",           "multiplier": 0.60},
    "us_holiday":         {"label": "US Holiday",                 "multiplier": 0.75},
}


# ===========================================================================
# FOR_FUTURE — used only by for_future/engine/ (Seat Allocation tab)
# Not referenced by any current Streamlit tab. Safe to leave as-is.
# ===========================================================================

# Allocation mode: "simple" (flat %) or "advanced" (attendance-based formula)
ALLOCATION_MODE = "simple"  # for_future: for_future/engine/allocation_engine.py

# Global seat allocation % (used in simple mode as default for all units)
DEFAULT_GLOBAL_ALLOC_PCT = 0.80  # for_future: allocation_engine

# Allocation policy bounds
MIN_ALLOC_PCT = 0.20  # for_future: allocation_engine — minimum allocation % per unit
MAX_ALLOC_PCT = 1.50  # for_future: allocation_engine — maximum allocation % per unit

# Buffer and scaling
PEAK_BUFFER_MULTIPLIER = 1.0  # for_future: allocation_engine

# Planning horizons (months)
PLANNING_HORIZONS = [3, 6]       # for_future: scenario_engine
DEFAULT_PLANNING_HORIZON = 6     # for_future: scenario_engine

# Scenario types
SCENARIO_TYPES = [               # for_future: scenario_engine / Scenario dataclass
    "baseline",
    "growth",
    "efficiency",
    "attrition",
    "consolidation",
    "custom",
]

# Spatial scoring weights — for_future: for_future/engine/spatial.py
ADJACENCY_BONUS_SAME_FLOOR = 100
ADJACENCY_BONUS_ADJACENT_FLOOR = 60
ADJACENCY_BONUS_SAME_TOWER = 30
ADJACENCY_BONUS_SAME_BUILDING = 15
ADJACENCY_BONUS_CROSS_BUILDING = 0
FRAGMENTATION_PENALTY_PER_FLOOR = 30

# Seat gap risk thresholds — for_future: spatial.py / explainer.py
RISK_RED_GAP_PCT = -0.10
RISK_RED_FRAGMENTATION = 0.7
RISK_AMBER_GAP_PCT = -0.05
RISK_AMBER_FRAGMENTATION = 0.5

# Floor saturation thresholds — for_future: spatial.py
FLOOR_SATURATION_THRESHOLD = 0.90  # Above this = floor is saturated
FLOOR_SURPLUS_THRESHOLD = 0.80     # Below this = surplus capacity

# Unit shortfall alert threshold — for_future: allocation_engine
UNIT_SHORTFALL_THRESHOLD = -0.10

# Scarcity redistribution — for_future: allocation_engine
SHRINK_CONTRIBUTION_FACTOR = 0.5  # How much of shrinkage is released to pool

# Priority ordering for scarcity allocation — for_future: allocation_engine
PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, None: 3}

# RTO utilization alert threshold — for_future: allocation_engine
RTO_UTILIZATION_THRESHOLD = 0.20

# Planning buffer presets — for_future: allocation_engine (Advanced mode)
PLANNING_BUFFER_PRESETS = {
    "lean":         {"peak_buffer_multiplier": 0.7, "shrink_contribution_factor": 0.7},
    "balanced":     {"peak_buffer_multiplier": 1.0, "shrink_contribution_factor": 0.5},
    "conservative": {"peak_buffer_multiplier": 1.4, "shrink_contribution_factor": 0.3},
}
DEFAULT_PLANNING_BUFFER = "balanced"  # for_future: allocation_engine
