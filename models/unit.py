from dataclasses import dataclass
from typing import Optional


@dataclass
class Unit:
    unit_name: str
    current_total_hc: int
    hc_growth_pct: float          # e.g. 0.10 for 10% net growth (positive = growth, negative = shrink)
    business_priority: Optional[str] = None  # "High", "Medium", "Low"
    seat_alloc_pct: Optional[float] = None   # Per-unit alloc % override (simple mode)
    night_shift_pct: float = 0.0             # 0.0–1.0, fraction of HC on night shift (hot-seating)

    @property
    def net_hc_change_pct(self) -> float:
        return self.hc_growth_pct

    def projected_hc(self, horizon_months: int) -> float:
        """Project HC over planning horizon."""
        monthly_net = self.net_hc_change_pct / 12
        return self.current_total_hc * (1 + monthly_net * horizon_months)
