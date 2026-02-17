"""Tests for the PuLP optimizer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.building import Floor
from models.unit import Unit
from models.allocation import AllocationRecommendation, FloorAssignment
from engine.optimizer import optimize_allocation


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


def make_unit(name="Eng", hc=200):
    return Unit(name, hc, 0.05, 0.05)


class TestOptimizer:
    def test_min_shortfall_feasible(self):
        floors = [make_floor(floor_num=i, seats=100) for i in range(1, 4)]
        allocs = [make_alloc(name="A", demand=100), make_alloc(name="B", demand=80)]
        baseline = [
            FloorAssignment("A", "B1", "B1-T1", 1, 100, "same_floor"),
            FloorAssignment("B", "B1", "B1-T1", 2, 80, "same_floor"),
        ]
        units = [make_unit("A", 200), make_unit("B", 150)]

        result = optimize_allocation(
            allocs, floors, baseline, objective="min_shortfall", units=units,
        )
        assert "Optimal" in result.status
        total = sum(result.unit_allocations.values())
        assert total > 0

    def test_min_floors(self):
        floors = [make_floor(floor_num=i, seats=200) for i in range(1, 4)]
        allocs = [make_alloc(name="A", demand=80)]
        baseline = [FloorAssignment("A", "B1", "B1-T1", 1, 40, "same_floor"),
                     FloorAssignment("A", "B1", "B1-T1", 2, 40, "same_floor")]
        units = [make_unit("A", 200)]

        result = optimize_allocation(
            allocs, floors, baseline, objective="min_floors", units=units,
        )
        assert "Optimal" in result.status
        # Should consolidate onto fewer floors
        new_floors = len(set((a.tower_id, a.floor_number) for a in result.assignments if a.unit_name == "A"))
        assert new_floors <= 2

    def test_fair_allocation(self):
        floors = [make_floor(floor_num=i, seats=100) for i in range(1, 3)]
        allocs = [make_alloc(name="A", demand=120), make_alloc(name="B", demand=120)]
        baseline = []
        units = [make_unit("A", 200), make_unit("B", 200)]

        result = optimize_allocation(
            allocs, floors, baseline, objective="fair_allocation", units=units,
        )
        assert "Optimal" in result.status
        # Both should get roughly equal allocation
        a_seats = result.unit_allocations.get("A", 0)
        b_seats = result.unit_allocations.get("B", 0)
        assert abs(a_seats - b_seats) <= 10  # Roughly fair


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
