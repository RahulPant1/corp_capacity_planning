"""CPG Seat Planning & Scenario Intelligence Platform — Streamlit entry point."""

import streamlit as st
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from components.sidebar import render_sidebar
from data.session_store import initialize_session_state
from tabs import (
    tab_executive_dashboard,
    tab_unit_impact,
    tab_spatial_floor,
    tab_scenario_lab,
    tab_optimization,
    tab_admin_governance,
)


def main():
    st.set_page_config(
        page_title="CPG Seat Planning",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    initialize_session_state()
    sidebar_state = render_sidebar()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Executive Dashboard",
        "👥 Unit Impact View",
        "🏗️ Spatial / Floor View",
        "🧪 Scenario Lab",
        "⚡ Optimization",
        "⚙️ Admin & Governance",
    ])

    with tab1:
        tab_executive_dashboard.render(sidebar_state)
    with tab2:
        tab_unit_impact.render(sidebar_state)
    with tab3:
        tab_spatial_floor.render(sidebar_state)
    with tab4:
        tab_scenario_lab.render(sidebar_state)
    with tab5:
        tab_optimization.render(sidebar_state)
    with tab6:
        tab_admin_governance.render(sidebar_state)


if __name__ == "__main__":
    main()
