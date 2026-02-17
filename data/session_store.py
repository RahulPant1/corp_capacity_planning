"""Typed wrapper around st.session_state for application data."""

import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime
from models.building import Floor
from models.unit import Unit
from models.attendance import AttendanceProfile
from models.scenario import Scenario, ScenarioParams
from models.allocation import AllocationRecommendation, FloorAssignment
from models.audit import AuditEntry


def initialize_session_state():
    """Initialize all session state keys with defaults."""
    defaults = {
        "floors": [],
        "units": [],
        "attendance": [],
        "scenarios": {},
        "active_scenario_id": "baseline",
        "audit_log": [],
        "data_loaded": False,
        "rule_config": {
            "allocation_mode": "simple",
            "global_alloc_pct": 0.80,
            "min_alloc_pct": 0.20,
            "max_alloc_pct": 1.50,
            "stability_discount_threshold": 0.7,
            "stability_discount_factor": 0.30,
            "peak_buffer_multiplier": 1.0,
            "shrink_contribution_factor": 0.5,
        },
        "sidebar_state": {
            "scenario_id": "baseline",
            "planning_horizon": 6,
            "mode": "View",
        },
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


# --- Getters ---

def get_floors() -> List[Floor]:
    return st.session_state.get("floors", [])


def get_units() -> List[Unit]:
    return st.session_state.get("units", [])


def get_attendance() -> List[AttendanceProfile]:
    return st.session_state.get("attendance", [])


def get_scenarios() -> Dict[str, Scenario]:
    return st.session_state.get("scenarios", {})


def get_active_scenario_id() -> str:
    return st.session_state.get("active_scenario_id", "baseline")


def get_active_scenario() -> Optional[Scenario]:
    scenarios = get_scenarios()
    return scenarios.get(get_active_scenario_id())


def get_audit_log() -> List[AuditEntry]:
    return st.session_state.get("audit_log", [])


def get_rule_config() -> dict:
    return st.session_state.get("rule_config", {})


def is_data_loaded() -> bool:
    return st.session_state.get("data_loaded", False)


# --- Setters ---

def set_floors(floors: List[Floor]):
    st.session_state["floors"] = floors


def set_units(units: List[Unit]):
    st.session_state["units"] = units


def set_attendance(attendance: List[AttendanceProfile]):
    st.session_state["attendance"] = attendance


def set_data_loaded(loaded: bool):
    st.session_state["data_loaded"] = loaded


def set_active_scenario_id(scenario_id: str):
    st.session_state["active_scenario_id"] = scenario_id
    st.session_state["sidebar_state"]["scenario_id"] = scenario_id


def set_rule_config(config: dict):
    st.session_state["rule_config"] = config


# --- Scenario Management ---

def add_scenario(scenario: Scenario):
    st.session_state["scenarios"][scenario.scenario_id] = scenario


def remove_scenario(scenario_id: str):
    st.session_state["scenarios"].pop(scenario_id, None)
    if get_active_scenario_id() == scenario_id:
        set_active_scenario_id("baseline")


def update_scenario(scenario: Scenario):
    st.session_state["scenarios"][scenario.scenario_id] = scenario


def create_baseline_scenario(planning_horizon: int = 6) -> Scenario:
    """Create and store the baseline scenario."""
    scenario = Scenario(
        scenario_id="baseline",
        name="Baseline",
        description="Current state baseline scenario",
        scenario_type="baseline",
        planning_horizon_months=planning_horizon,
    )
    add_scenario(scenario)
    return scenario


# --- Audit ---

def add_audit_entry(
    action: str,
    scenario_id: str,
    field_changed: str,
    old_value: str,
    new_value: str,
    unit_name: Optional[str] = None,
    rationale: str = "",
):
    entry = AuditEntry(
        timestamp=datetime.now(),
        action=action,
        scenario_id=scenario_id,
        unit_name=unit_name,
        field_changed=field_changed,
        old_value=old_value,
        new_value=new_value,
        rationale=rationale,
    )
    st.session_state["audit_log"].append(entry)
