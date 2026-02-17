from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AuditEntry:
    timestamp: datetime
    action: str              # "override", "lock", "accept_optimization", "upload", "reset"
    scenario_id: str
    unit_name: Optional[str]
    field_changed: str
    old_value: str
    new_value: str
    rationale: str = ""
