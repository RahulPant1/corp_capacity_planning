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
        # Show lock icon for locked scenarios
        def _scenario_label(sid):
            s = scenarios.get(sid)
            if s is None:
                return sid
            return f"{s.name} 🔒" if s.is_locked else s.name

        scenario_ids = list(scenarios.keys()) if scenarios else ["baseline"]

        current_id = get_active_scenario_id()
        if current_id not in scenario_ids and scenario_ids:
            current_id = scenario_ids[0]

        selected_idx = scenario_ids.index(current_id) if current_id in scenario_ids else 0
        selected_id = st.selectbox(
            "Active Scenario",
            options=scenario_ids,
            format_func=_scenario_label,
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
            if active.is_locked:
                st.caption("🔒 Locked — edits disabled")
            if active.unit_overrides:
                st.caption(f"Overrides: {len(active.unit_overrides)} units")
            if active.last_run_at:
                st.caption(f"Last run: {active.last_run_at.strftime('%b %d, %H:%M')}")
            else:
                st.caption("Not yet run — go to What-If Analysis")

    return SidebarState(
        scenario_id=selected_id,
        planning_horizon=horizon,
    )
