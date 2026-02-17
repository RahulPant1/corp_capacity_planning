"""Tests for the allocation engine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.unit import Unit
from models.attendance import AttendanceProfile
from models.building import Floor
from engine.allocation_engine import (
    compute_recommended_allocation,
    compute_simple_allocation,
    compute_all_allocations,
    distribute_seats,
    run_allocation,
)


def make_unit(name="Engineering", hc=400, growth=0.15, attrition=0.08, priority="High"):
    return Unit(name, hc, growth, attrition, priority)


def make_attendance(name="Engineering", median=250, max_hc=320, rto=3.5):
    return AttendanceProfile(name, median, max_hc, rto)


def make_floor(building="B1", tower="B1-T1", floor_num=1, seats=100):
    return Floor(building, "HQ", tower, floor_num, seats)


class TestComputeRecommendedAllocation:
    def test_basic_allocation(self):
        unit = make_unit()
        att = make_attendance()
        result = compute_recommended_allocation(unit, att, horizon_months=6)

        assert result.unit_name == "Engineering"
        assert result.recommended_alloc_pct > 0
        assert result.effective_demand_seats > 0
        assert len(result.explanation_steps) >= 5

    def test_zero_headcount(self):
        unit = make_unit(hc=0)
        att = make_attendance(median=0, max_hc=0)
        result = compute_recommended_allocation(unit, att, horizon_months=6)

        assert result.recommended_alloc_pct == 0
        assert result.effective_demand_seats == 0

    def test_high_growth_increases_allocation(self):
        unit_low = make_unit(growth=0.02)
        unit_high = make_unit(growth=0.30)
        att = make_attendance()

        result_low = compute_recommended_allocation(unit_low, att, horizon_months=6)
        result_high = compute_recommended_allocation(unit_high, att, horizon_months=6)

        assert result_high.recommended_alloc_pct >= result_low.recommended_alloc_pct

    def test_high_attrition_decreases_allocation(self):
        unit_low_att = make_unit(attrition=0.02)
        unit_high_att = make_unit(attrition=0.25)
        att = make_attendance()

        result_low = compute_recommended_allocation(unit_low_att, att, horizon_months=6)
        result_high = compute_recommended_allocation(unit_high_att, att, horizon_months=6)

        assert result_high.recommended_alloc_pct <= result_low.recommended_alloc_pct

    def test_clamped_to_policy_bounds(self):
        # Very low demand should clamp to min
        unit = make_unit(hc=100, growth=0.0, attrition=0.0)
        att = make_attendance(name="Engineering", median=5, max_hc=6, rto=1.0)
        config = {"min_alloc_pct": 0.20, "max_alloc_pct": 1.50}

        result = compute_recommended_allocation(unit, att, horizon_months=6, rule_config=config)
        assert result.recommended_alloc_pct >= 0.20


class TestDistributeSeats:
    def test_no_scarcity(self):
        allocs = [
            compute_recommended_allocation(make_unit(hc=100), make_attendance(median=60, max_hc=70, name="Engineering"), 6),
        ]
        allocs[0].effective_demand_seats = 50
        units = [make_unit(hc=100)]

        result = distribute_seats(allocs, units, total_supply=200)
        assert result[0].allocated_seats == 50
        assert result[0].seat_gap == 0

    def test_scarcity_distributes_proportionally(self):
        u1 = make_unit(name="A", hc=100, growth=0.1, attrition=0.0, priority="High")
        u2 = make_unit(name="B", hc=100, growth=0.0, attrition=0.1, priority="Low")
        att1 = make_attendance(name="A", median=80, max_hc=90)
        att2 = make_attendance(name="B", median=80, max_hc=90)

        allocs = compute_all_allocations([u1, u2], {"A": att1, "B": att2}, 6)
        total_demand = sum(a.effective_demand_seats for a in allocs)

        # Supply less than demand
        result = distribute_seats(allocs, [u1, u2], total_supply=50)
        total_allocated = sum(a.allocated_seats for a in result)
        assert total_allocated <= 50


class TestRunAllocation:
    def test_full_pipeline(self):
        units = [
            make_unit(name="Eng", hc=200, growth=0.10, attrition=0.05),
            make_unit(name="Sales", hc=100, growth=0.02, attrition=0.08),
        ]
        att_map = {
            "Eng": make_attendance(name="Eng", median=140, max_hc=170, rto=3.5),
            "Sales": make_attendance(name="Sales", median=60, max_hc=75, rto=3.0),
        }
        floors = [make_floor(floor_num=i, seats=100) for i in range(1, 6)]

        results = run_allocation(units, att_map, floors, horizon_months=6)
        assert len(results) == 2
        total_allocated = sum(r.allocated_seats for r in results)
        assert total_allocated > 0
        assert total_allocated <= 500  # 5 floors * 100 seats


class TestSimpleAllocation:
    def test_basic_flat_allocation(self):
        unit = make_unit(hc=400, growth=0.0, attrition=0.0)
        config = {"global_alloc_pct": 0.80, "min_alloc_pct": 0.20, "max_alloc_pct": 1.50}
        result = compute_simple_allocation(unit, horizon_months=6, rule_config=config)

        assert abs(result.recommended_alloc_pct - 0.80) < 0.01
        assert result.effective_demand_seats == 320  # 80% of 400

    def test_per_unit_override(self):
        unit = make_unit(hc=400, growth=0.0, attrition=0.0)
        unit.seat_alloc_pct = 0.90  # Override to 90%
        config = {"global_alloc_pct": 0.80, "min_alloc_pct": 0.20, "max_alloc_pct": 1.50}
        result = compute_simple_allocation(unit, horizon_months=6, rule_config=config)

        assert abs(result.recommended_alloc_pct - 0.90) < 0.01
        assert result.effective_demand_seats == 360  # 90% of 400

    def test_growth_adjustment(self):
        unit = make_unit(hc=400, growth=0.15, attrition=0.08)
        config = {"global_alloc_pct": 0.80, "min_alloc_pct": 0.20, "max_alloc_pct": 1.50}
        result = compute_simple_allocation(unit, horizon_months=6, rule_config=config)

        # net change = 7%, over 6mo = 3.5%, so alloc = 0.80 * 1.035 = 0.828
        assert result.recommended_alloc_pct > 0.80
        assert result.recommended_alloc_pct < 0.85

    def test_clamping_to_min(self):
        unit = make_unit(hc=400, growth=0.0, attrition=0.30)  # Heavy attrition
        config = {"global_alloc_pct": 0.30, "min_alloc_pct": 0.20, "max_alloc_pct": 1.50}
        result = compute_simple_allocation(unit, horizon_months=6, rule_config=config)

        assert result.recommended_alloc_pct >= 0.20

    def test_zero_headcount(self):
        unit = make_unit(hc=0)
        config = {"global_alloc_pct": 0.80}
        result = compute_simple_allocation(unit, horizon_months=6, rule_config=config)

        assert result.recommended_alloc_pct == 0
        assert result.effective_demand_seats == 0

    def test_mode_routing_simple(self):
        """compute_all_allocations should use simple mode when configured."""
        units = [make_unit(hc=200, growth=0.0, attrition=0.0)]
        att_map = {"Engineering": make_attendance()}
        config = {"allocation_mode": "simple", "global_alloc_pct": 0.80,
                  "min_alloc_pct": 0.20, "max_alloc_pct": 1.50}

        results = compute_all_allocations(units, att_map, 6, rule_config=config)
        assert len(results) == 1
        # In simple mode, alloc should be exactly 80% (no growth/attrition)
        assert abs(results[0].recommended_alloc_pct - 0.80) < 0.01

    def test_mode_routing_advanced(self):
        """compute_all_allocations should use advanced mode when configured."""
        units = [make_unit(hc=400, growth=0.15, attrition=0.08)]
        att_map = {"Engineering": make_attendance()}
        config = {"allocation_mode": "advanced", "min_alloc_pct": 0.20, "max_alloc_pct": 1.50}

        results = compute_all_allocations(units, att_map, 6, rule_config=config)
        assert len(results) == 1
        # Advanced mode should NOT be exactly 80% — it derives from attendance
        assert results[0].recommended_alloc_pct != 0.80


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
