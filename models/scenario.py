from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ScenarioOverride:
    unit_name: str
    hc_growth_pct: Optional[float] = None
    median_hc: Optional[float] = None
    max_hc: Optional[float] = None
    avg_rto_days: Optional[float] = None
    alloc_pct_override: Optional[float] = None


@dataclass
class ScenarioParams:
    global_rto_mandate_days: Optional[float] = None
    excluded_floors: List[str] = field(default_factory=list)
    capacity_reduction_pct: float = 0.0
    # Optimizer constraints — persisted when Accept & Apply is used
    optimizer_objective: Optional[str] = None    # "optimal_placement" | "rto_based" | "rto_whatif"
    max_floors_per_unit: Optional[int] = None
    pinned_tower_ids: Optional[dict] = None      # {unit_name: [tower_id, ...]}
    min_guarantee_pct: Optional[float] = None    # Each unit gets at least this fraction of its demand


@dataclass
class Scenario:
    scenario_id: str
    name: str
    description: str
    scenario_type: str  # "baseline", "growth", "efficiency", "attrition", "consolidation", "custom"
    planning_horizon_months: int = 6
    created_at: datetime = field(default_factory=datetime.now)
    is_locked: bool = False
    unit_overrides: Dict[str, ScenarioOverride] = field(default_factory=dict)
    params: ScenarioParams = field(default_factory=ScenarioParams)
    allocation_results: List = field(default_factory=list)
    floor_assignments: List = field(default_factory=list)
    last_run_at: Optional[datetime] = None
