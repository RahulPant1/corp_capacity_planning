"""Tests for the PuLP optimizer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.building import Floor
from models.unit import Unit
from models.allocation import AllocationRecommendation, FloorAssignment
from models.attendance import AttendanceProfile
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


def make_attendance(name="Eng", median=150, max_hc=180, rto=3.5):
    return AttendanceProfile(name, median, max_hc, rto)


class TestOptimizer:
    def test_optimal_placement_respects_demand_cap(self):
        """Units should get at most their effective_demand_seats."""
        floors = [make_floor(floor_num=i, seats=200) for i in range(1, 4)]
        allocs = [make_alloc(name="A", demand=100), make_alloc(name="B", demand=80)]
        baseline = [
            FloorAssignment("A", "B1", "B1-T1", 1, 100, "same_floor"),
            FloorAssignment("B", "B1", "B1-T1", 2, 80, "same_floor"),
        ]
        units = [make_unit("A", 200), make_unit("B", 150)]

        result = optimize_allocation(
            allocs, floors, baseline, objective="optimal_placement", units=units,
        )
        assert "Optimal" in result.status
        assert result.unit_allocations["A"] <= 100  # capped at demand
        assert result.unit_allocations["B"] <= 80

    def test_optimal_placement_consolidates_floors(self):
        """Should consolidate units onto fewer floors."""
        floors = [make_floor(floor_num=i, seats=200) for i in range(1, 4)]
        allocs = [make_alloc(name="A", demand=80)]
        baseline = [
            FloorAssignment("A", "B1", "B1-T1", 1, 40, "same_floor"),
            FloorAssignment("A", "B1", "B1-T1", 2, 40, "same_floor"),
        ]
        units = [make_unit("A", 200)]

        result = optimize_allocation(
            allocs, floors, baseline, objective="optimal_placement", units=units,
        )
        assert "Optimal" in result.status
        new_floors = len(set(
            (a.tower_id, a.floor_number) for a in result.assignments if a.unit_name == "A"
        ))
        assert new_floors == 1  # should fit on one floor

    def test_rto_based_uses_attendance_demand(self):
        """RTO-based should use attendance data, not allocation rule demand."""
        floors = [make_floor(floor_num=i, seats=200) for i in range(1, 4)]
        # Allocation rule says 160 seats, but attendance says ~100
        allocs = [make_alloc(name="A", demand=160)]
        baseline = [FloorAssignment("A", "B1", "B1-T1", 1, 160, "same_floor")]
        units = [make_unit("A", 200)]
        att_map = {"A": make_attendance("A", median=120, max_hc=140, rto=3.5)}
        # RTO demand = (120 + (140-120)*1.0) * (3.5/5) = 140 * 0.7 = 98

        result = optimize_allocation(
            allocs, floors, baseline, objective="rto_based",
            units=units, attendance_map=att_map,
        )
        assert "Optimal" in result.status
        assert result.unit_allocations["A"] <= 100  # ~98, capped at RTO demand
        assert result.unit_allocations["A"] < 160  # less than allocation rule
        assert result.savings_summary is not None
        assert result.savings_summary["seats_saved"] > 0

    def test_rto_whatif_uses_override_rto(self):
        """What-if RTO should use the target RTO, not actual."""
        floors = [make_floor(floor_num=i, seats=200) for i in range(1, 4)]
        allocs = [make_alloc(name="A", demand=160)]
        baseline = [FloorAssignment("A", "B1", "B1-T1", 1, 160, "same_floor")]
        units = [make_unit("A", 200)]
        att_map = {"A": make_attendance("A", median=120, max_hc=140, rto=3.5)}

        # With 3 days: (120 + 20) * (3/5) = 140 * 0.6 = 84
        result_3 = optimize_allocation(
            allocs, floors, baseline, objective="rto_whatif",
            units=units, attendance_map=att_map, target_rto_days=3.0,
        )
        # With 4 days: (120 + 20) * (4/5) = 140 * 0.8 = 112
        result_4 = optimize_allocation(
            allocs, floors, baseline, objective="rto_whatif",
            units=units, attendance_map=att_map, target_rto_days=4.0,
        )

        assert "Optimal" in result_3.status
        assert "Optimal" in result_4.status
        assert result_3.unit_allocations["A"] < result_4.unit_allocations["A"]

    def test_fair_distribution_under_scarcity(self):
        """When capacity is tight, units should still get fair distribution."""
        floors = [make_floor(floor_num=i, seats=100) for i in range(1, 3)]  # 200 total
        allocs = [make_alloc(name="A", demand=120), make_alloc(name="B", demand=120)]  # 240 demand
        baseline = []
        units = [make_unit("A", 200), make_unit("B", 200)]

        result = optimize_allocation(
            allocs, floors, baseline, objective="optimal_placement", units=units,
        )
        assert "Optimal" in result.status
        a_seats = result.unit_allocations.get("A", 0)
        b_seats = result.unit_allocations.get("B", 0)
        assert a_seats + b_seats <= 200  # respects total capacity
        assert abs(a_seats - b_seats) <= 10  # roughly fair


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
