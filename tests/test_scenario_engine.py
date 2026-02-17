"""Tests for the scenario engine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.unit import Unit
from models.attendance import AttendanceProfile
from models.building import Floor
from models.scenario import Scenario, ScenarioOverride, ScenarioParams
from engine.scenario_engine import apply_overrides, apply_floor_modifications, run_scenario


def make_unit(name="Eng", hc=200, growth=0.10, attrition=0.05):
    return Unit(name, hc, growth, attrition, "High")


def make_attendance(name="Eng", median=140, max_hc=170, rto=3.5):
    return AttendanceProfile(name, median, max_hc, rto, 0.7)


def make_floor(tower="B1-T1", floor_num=1, seats=100):
    return Floor("B1", "HQ", tower, floor_num, seats)


class TestApplyOverrides:
    def test_growth_override(self):
        units = [make_unit()]
        att_map = {"Eng": make_attendance()}
        scenario = Scenario("test", "Test", "", "custom")
        scenario.unit_overrides = {
            "Eng": ScenarioOverride(unit_name="Eng", hc_growth_pct=0.25)
        }

        mod_units, mod_att = apply_overrides(units, att_map, scenario)
        assert mod_units[0].hc_growth_pct == 0.25
        assert units[0].hc_growth_pct == 0.10  # Original unchanged

    def test_rto_mandate(self):
        units = [make_unit()]
        att_map = {"Eng": make_attendance(rto=2.0)}
        scenario = Scenario("test", "Test", "", "custom")
        scenario.params.global_rto_mandate_days = 4.0

        _, mod_att = apply_overrides(units, att_map, scenario)
        assert mod_att["Eng"].avg_rto_days_per_week == 4.0  # Raised to mandate


class TestApplyFloorModifications:
    def test_exclude_floors(self):
        floors = [make_floor(floor_num=1), make_floor(floor_num=2)]
        scenario = Scenario("test", "Test", "", "custom")
        scenario.params.excluded_floors = ["B1-T1-F1"]

        result = apply_floor_modifications(floors, scenario)
        assert len(result) == 1
        assert result[0].floor_number == 2

    def test_capacity_reduction(self):
        floors = [make_floor(seats=100)]
        scenario = Scenario("test", "Test", "", "custom")
        scenario.params.capacity_reduction_pct = 0.20

        result = apply_floor_modifications(floors, scenario)
        assert result[0].total_seats == 80


class TestRunScenario:
    def test_full_scenario_run(self):
        units = [make_unit(name="A", hc=100), make_unit(name="B", hc=100)]
        att_map = {
            "A": make_attendance(name="A", median=70, max_hc=85),
            "B": make_attendance(name="B", median=60, max_hc=75),
        }
        floors = [make_floor(floor_num=i, seats=100) for i in range(1, 4)]
        scenario = Scenario("test", "Test", "", "custom", planning_horizon_months=6)

        result = run_scenario(scenario, units, att_map, floors)
        assert len(result.allocation_results) == 2
        assert len(result.floor_assignments) > 0
        total_alloc = sum(a.allocated_seats for a in result.allocation_results)
        assert total_alloc > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
