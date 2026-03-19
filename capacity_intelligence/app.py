"""Capacity Intelligence — Limited Version
Run with:  streamlit run capacity_intelligence/app.py
"""

import sys
import os

# Make sure local sub-packages are importable regardless of working directory
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import streamlit as st

# ---------------------------------------------------------------------------
# Page config  (must be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Capacity Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stMetric label { font-size: 0.78rem !important; }
    .insight-box {
        background: #f8f9fa;
        border-left: 4px solid #1a3c5e;
        padding: 0.9rem 1.1rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        font-size: 0.88rem;
    }
    .section-header {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6c757d;
        margin-bottom: 0.3rem;
        margin-top: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "ci_data_loaded": False,
    "ci_daily_df": None,
    "ci_buildings_meta": None,
    "ci_data_source": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.caption("Run: `streamlit run capacity_intelligence/app.py`")

# ---------------------------------------------------------------------------
# App header
# ---------------------------------------------------------------------------
col_h1, _ = st.columns([6, 1])
with col_h1:
    st.markdown("## 📊 Capacity Intelligence")
    st.caption("Transforming predictive footfall data into actionable operational interfaces.")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
_t_short, _t_long, _t_scenario, _t_admin, _t_help = st.tabs([
    "📅 Short-Term View",
    "📈 Long-Term View",
    "🔀 Scenario Planner",
    "⚙️ Admin",
    "📖 Help",
])

from tabs import tab_short_term, tab_long_term, tab_scenario_planner, tab_admin, tab_help

with _t_short:
    tab_short_term.render()

with _t_long:
    tab_long_term.render()

with _t_scenario:
    tab_scenario_planner.render()

with _t_admin:
    tab_admin.render()

with _t_help:
    tab_help.render()
