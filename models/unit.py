from dataclasses import dataclass
from typing import Optional


@dataclass
class Unit:
    unit_name: str
    current_total_hc: int
    hc_growth_pct: float          # e.g. 0.10 for 10%
    attrition_pct: float          # e.g. 0.05 for 5%
    business_priority: Optional[str] = None  # "High", "Medium", "Low"

    @property
    def net_hc_change_pct(self) -> float:
        return self.hc_growth_pct - self.attrition_pct

    def projected_hc(self, horizon_months: int) -> float:
        """Project HC over planning horizon."""
        monthly_net = self.net_hc_change_pct / 12
        return self.current_total_hc * (1 + monthly_net * horizon_months)
