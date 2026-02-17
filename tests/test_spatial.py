"""Tests for the spatial engine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.building import Floor
from models.allocation import AllocationRecommendation, FloorAssignment
from engine.spatial import (
    assign_units_to_floors,
    get_floor_utilization,
    get_consolidation_suggestions,
    compute_adjacency_tier,
)


def make_floor(tower="B1-T1", floor_num=1, seats=100):
    return Floor("B1", "HQ", tower, floor_num, seats)


def make_alloc(name="Eng", demand=80, allocated=80):
    return AllocationRecommendation(
        unit_name=name,
        recommended_alloc_pct=0.7,
        effective_demand_seats=demand,
        allocated_seats=allocated,
        seat_gap=0,
        fragmentation_score=0.0,
    )


class TestAssignUnitsToFloors:
    def test_single_unit_single_floor(self):
        floors = [make_floor(seats=200)]
        allocs = [make_alloc(allocated=80)]

        assignments, frag = assign_units_to_floors(allocs, floors)
        assert len(assignments) == 1
        assert assignments[0].seats_assigned == 80
        assert frag["Eng"] < 0.5  # Not fragmented

    def test_unit_spans_multiple_floors(self):
        floors = [make_floor(floor_num=1, seats=50), make_floor(floor_num=2, seats=50)]
        allocs = [make_alloc(allocated=80)]

        assignments, frag = assign_units_to_floors(allocs, floors)
        total = sum(a.seats_assigned for a in assignments)
        assert total == 80
        assert len(assignments) == 2

    def test_excluded_floors(self):
        floors = [make_floor(floor_num=1, seats=100), make_floor(floor_num=2, seats=100)]
        allocs = [make_alloc(allocated=50)]

        assignments, _ = assign_units_to_floors(allocs, floors, excluded_floor_ids=["B1-T1-F1"])
        assert all(a.floor_number != 1 for a in assignments)

    def test_multiple_units(self):
        floors = [make_floor(floor_num=i, seats=100) for i in range(1, 4)]
        allocs = [make_alloc(name="A", allocated=120), make_alloc(name="B", allocated=80)]

        assignments, _ = assign_units_to_floors(allocs, floors)
        total_a = sum(a.seats_assigned for a in assignments if a.unit_name == "A")
        total_b = sum(a.seats_assigned for a in assignments if a.unit_name == "B")
        assert total_a == 120
        assert total_b == 80


class TestFloorUtilization:
    def test_utilization_calculation(self):
        floors = [make_floor(seats=100)]
        assignments = [FloorAssignment("Eng", "B1", "B1-T1", 1, 60, "same_floor")]

        util = get_floor_utilization(floors, assignments)
        assert len(util) == 1
        assert util[0]["used_seats"] == 60
        assert util[0]["available_seats"] == 40
        assert abs(util[0]["utilization_pct"] - 0.6) < 0.01


class TestAdjacencyTier:
    def test_same_floor(self):
        f = make_floor(floor_num=3)
        existing = [FloorAssignment("Eng", "B1", "B1-T1", 3, 50, "same_floor")]
        tier, bonus = compute_adjacency_tier(f, existing, "Eng")
        assert tier == "same_floor"
        assert bonus == 100

    def test_adjacent_floor(self):
        f = make_floor(floor_num=4)
        existing = [FloorAssignment("Eng", "B1", "B1-T1", 3, 50, "same_floor")]
        tier, bonus = compute_adjacency_tier(f, existing, "Eng")
        assert tier == "adjacent"
        assert bonus == 60

    def test_cross_tower(self):
        f = make_floor(tower="B1-T2", floor_num=1)
        existing = [FloorAssignment("Eng", "B1", "B1-T1", 3, 50, "same_floor")]
        tier, bonus = compute_adjacency_tier(f, existing, "Eng")
        assert tier == "cross_tower"
        assert bonus == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
