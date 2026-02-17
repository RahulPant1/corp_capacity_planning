"""Global sidebar controls for scenario and horizon selection."""

import streamlit as st
from dataclasses import dataclass
from data.session_store import get_scenarios, get_active_scenario_id, set_active_scenario_id
from config.defaults import PLANNING_HORIZONS, DEFAULT_PLANNING_HORIZON


@dataclass
class SidebarState:
    scenario_id: str
    planning_horizon: int


def render_sidebar() -> SidebarState:
    """Render the global sidebar controls and return current state."""
    with st.sidebar:
        st.title("CPG Seat Planning")
        st.divider()

        # Scenario selector
        scenarios = get_scenarios()
        scenario_names = {sid: s.name for sid, s in scenarios.items()} if scenarios else {"baseline": "Baseline"}
        scenario_ids = list(scenario_names.keys())

        current_id = get_active_scenario_id()
        if current_id not in scenario_ids and scenario_ids:
            current_id = scenario_ids[0]

        selected_idx = scenario_ids.index(current_id) if current_id in scenario_ids else 0
        selected_id = st.selectbox(
            "Active Scenario",
            options=scenario_ids,
            format_func=lambda x: scenario_names.get(x, x),
            index=selected_idx,
            key="sidebar_scenario",
        )

        if selected_id != get_active_scenario_id():
            set_active_scenario_id(selected_id)

        # Planning horizon
        horizon = st.selectbox(
            "Planning Horizon (months)",
            options=PLANNING_HORIZONS,
            index=PLANNING_HORIZONS.index(DEFAULT_PLANNING_HORIZON),
            key="sidebar_horizon",
        )

        st.divider()

        # Data status indicator
        from data.session_store import is_data_loaded
        if is_data_loaded():
            st.success("Data loaded")
        else:
            st.warning("No data loaded — go to Admin tab")

        # Active scenario info
        active = scenarios.get(selected_id)
        if active:
            st.caption(f"Type: {active.scenario_type}")
            st.caption(f"Locked: {'Yes' if active.is_locked else 'No'}")
            if active.unit_overrides:
                st.caption(f"Overrides: {len(active.unit_overrides)} units")

    return SidebarState(
        scenario_id=selected_id,
        planning_horizon=horizon,
    )
