from dataclasses import dataclass


@dataclass
class Floor:
    building_id: str
    building_name: str
    tower_id: str
    floor_number: int
    total_seats: int

    @property
    def floor_id(self) -> str:
        return f"{self.tower_id}-F{self.floor_number}"


@dataclass
class FloorAllocation:
    """Result of allocating a unit to a specific floor."""
    floor: Floor
    unit_name: str
    allocated_seats: int
    scenario_id: str
