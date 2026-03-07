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
    tab_optimization,
    tab_admin_governance,
    tab_forecasting,
    tab_floor_sandbox,
)


def main():
    st.set_page_config(
        page_title="CPG Seat Planning",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    initialize_session_state()

    st.markdown("""
<style>
/* Hide the Streamlit top toolbar to reclaim vertical space */
header[data-testid="stHeader"] { display: none !important; }
/* Reduce top padding — safe now that header is hidden */
div.block-container, div[data-testid="stMainBlockContainer"] {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
}
/* Reduce interior padding inside each tab panel */
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 0.5rem !important;
}
/* Smaller tab labels so all 6 fit in one row */
button[data-baseweb="tab"] {
    font-size: 0.72rem !important;
    padding-left: 0.6rem !important;
    padding-right: 0.6rem !important;
}
/* Hide Streamlit footer to reduce bottom scroll */
footer { display: none !important; }
</style>
""", unsafe_allow_html=True)

    sidebar_state = render_sidebar()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Executive Dashboard",
        "🤖 What-If Analysis",
        "🏗️ Spatial / Floor View",
        "👥 Unit Impact View",
        "📈 Demand Analytics",
        "🗂️ Floor Plan Sandbox",
        "⚙️ Admin",
    ])

    with tab1:
        tab_executive_dashboard.render(sidebar_state)
    with tab2:
        tab_optimization.render(sidebar_state)
    with tab3:
        tab_spatial_floor.render(sidebar_state)
    with tab4:
        tab_unit_impact.render(sidebar_state)
    with tab5:
        tab_forecasting.render(sidebar_state)
    with tab6:
        tab_floor_sandbox.render(sidebar_state)
    with tab7:
        tab_admin_governance.render(sidebar_state)


if __name__ == "__main__":
    main()
