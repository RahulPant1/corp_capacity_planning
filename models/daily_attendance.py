"""Daily attendance record — one observation per unit per day."""

from dataclasses import dataclass
from datetime import date


@dataclass
class DailyAttendanceRecord:
    date: date
    unit_name: str
    in_office_count: int
