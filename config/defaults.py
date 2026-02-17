"""Default configuration constants for the CPG Seat Planning Platform."""

# Allocation mode: "simple" (flat %) or "advanced" (attendance-based formula)
ALLOCATION_MODE = "simple"

# Global seat allocation % (used in simple mode as default for all units)
DEFAULT_GLOBAL_ALLOC_PCT = 0.80

# Allocation policy bounds
MIN_ALLOC_PCT = 0.20  # Minimum allocation percentage per unit
MAX_ALLOC_PCT = 1.50  # Maximum allocation percentage per unit

# Buffer and scaling
STABILITY_DISCOUNT_THRESHOLD = 0.7  # Stability above this reduces peak buffer
STABILITY_DISCOUNT_FACTOR = 0.30    # How much to reduce peak buffer for stable units
PEAK_BUFFER_MULTIPLIER = 1.0        # Multiplier applied to peak buffer

# Planning horizons (months)
PLANNING_HORIZONS = [3, 6]
DEFAULT_PLANNING_HORIZON = 6

# Scenario types
SCENARIO_TYPES = [
    "baseline",
    "growth",
    "efficiency",
    "attrition",
    "consolidation",
    "custom",
]

# Spatial scoring weights
ADJACENCY_BONUS_SAME_FLOOR = 100
ADJACENCY_BONUS_ADJACENT_FLOOR = 60
ADJACENCY_BONUS_SAME_TOWER = 30
ADJACENCY_BONUS_CROSS_TOWER = 0
FRAGMENTATION_PENALTY_PER_FLOOR = 30

# Risk thresholds
RISK_RED_GAP_PCT = -0.10
RISK_RED_FRAGMENTATION = 0.7
RISK_AMBER_GAP_PCT = -0.05
RISK_AMBER_FRAGMENTATION = 0.5

# Floor saturation alert threshold
FLOOR_SATURATION_THRESHOLD = 0.90
FLOOR_SURPLUS_THRESHOLD = 0.80  # Below this = surplus capacity

# Unit shortfall alert threshold
UNIT_SHORTFALL_THRESHOLD = -0.10

# Scarcity redistribution
SHRINK_CONTRIBUTION_FACTOR = 0.5  # How much of shrinkage is released to pool

# Priority ordering for scarcity allocation
PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, None: 3}

# Mode options
MODES = ["View", "Simulate", "Optimize"]
DEFAULT_MODE = "View"

# Working days per week (for RTO ratio calculation)
WORKING_DAYS_PER_WEEK = 5
