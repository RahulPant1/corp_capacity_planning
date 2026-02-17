from dataclasses import dataclass
from typing import Optional


@dataclass
class AttendanceProfile:
    unit_name: str
    monthly_median_hc: float
    monthly_max_hc: float
    avg_rto_days_per_week: float   # e.g. 3.2
    attendance_stability: Optional[float] = None  # 0-1 scale, 1=very stable

    @property
    def peak_to_median_ratio(self) -> float:
        if self.monthly_median_hc == 0:
            return 1.0
        return self.monthly_max_hc / self.monthly_median_hc

    @property
    def rto_ratio(self) -> float:
        """Fraction of a 5-day week attended."""
        return self.avg_rto_days_per_week / 5.0
