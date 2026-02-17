from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AllocationRecommendation:
    unit_name: str
    recommended_alloc_pct: float    # e.g. 0.75 for 75%
    effective_demand_seats: int     # Seats actually needed
    allocated_seats: int            # Seats assigned
    seat_gap: int                   # allocated - effective_demand (negative = shortfall)
    fragmentation_score: float      # 0-1, higher = more fragmented
    explanation_steps: List[str] = field(default_factory=list)
    is_overridden: bool = False
    override_alloc_pct: Optional[float] = None
    override_rationale: str = ""


@dataclass
class FloorAssignment:
    unit_name: str
    building_id: str
    tower_id: str
    floor_number: int
    seats_assigned: int
    adjacency_tier: str  # "same_floor", "adjacent", "same_tower", "cross_tower"
