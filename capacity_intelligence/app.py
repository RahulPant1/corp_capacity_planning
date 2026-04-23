"""Capacity Intelligence — Limited Version
Run with:  streamlit run capacity_intelligence/app.py

Entry point. Responsibilities:
  1. Page config and global CSS
  2. Session state initialisation (all ci_* keys with safe defaults)
  3. Sidebar status display
  4. Tab list construction (conditional on feature flags)
  5. Delegating render() to each tab module

Adding a tab: see CLAUDE.md → "Adding a new tab".
Feature flags: see config/defaults.py → ENABLE_LONG_TERM_VIEW.
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
    .block-container { padding-top: 3rem; padding-bottom: 1rem; }

    /* Tighter widget labels */
    .stMultiSelect label, .stRadio label,
    .stSlider label, .stSelectbox label { font-size: 0.78rem !important; }

    /* Smaller metric values */
    .stMetric label  { font-size: 0.72rem !important; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    .stMetric [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }

    /* Compact tab section headers (### markdown) */
    h3 { font-size: 1rem !important; margin-top: 0.4rem !important; margin-bottom: 0.2rem !important; }

    /* Remove excess top margin on radio groups */
    .stRadio > div { gap: 0.25rem; }

    /* Compact divider spacing */
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }

    .insight-box {
        background: #f8f9fa;
        border-left: 4px solid #1a3c5e;
        padding: 0.6rem 0.9rem;
        border-radius: 4px;
        margin-bottom: 0.4rem;
        font-size: 0.83rem;
    }
    .section-header {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6c757d;
        margin-bottom: 0.2rem;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session-state initialisation
# All ci_* keys must be declared here so tabs can safely call .get() without
# KeyError on first render. Admin tab is the only place that writes these.
# Full key reference: CLAUDE.md → "Session state keys"
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "ci_data_loaded":           False,
    "ci_daily_df":              None,  # joined working DataFrame — all analytical tabs read this
    "ci_floor_capacity_df":     None,  # DS1 — Floor Capacity
    "ci_seat_allocation_df":    None,  # DS2 — Seat Allocation
    "ci_headcount_df":          None,  # DS3 — Total Headcount
    "ci_prediction_df":         None,  # DS4 — 60-Day Prediction
    "ci_buildings_meta":        None,  # building-level metadata list (derived from DS1)
    "ci_data_source":           None,  # "sample" or "upload"
    "ci_scenario_multipliers":  None,  # event multipliers; None = use DEFAULT_SCENARIO_MULTIPLIERS
    "ci_holiday_calendar":      None,  # DataFrame(Date, City, Holiday Type, Holiday Name) or None
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("#### 📊 Capacity Intelligence")
    st.caption("Predictive footfall → operational planning")
    st.divider()
    if st.session_state.get("ci_data_loaded"):
        df  = st.session_state["ci_daily_df"]
        src = st.session_state.get("ci_data_source", "upload")
        st.success(f"✅ {src} data active")
        st.caption(
            f"**{df['Building Name'].nunique()}** buildings · "
            f"**{df['LOB'].nunique()}** LOBs  \n"
            f"{df['Date'].min().date()} → {df['Date'].max().date()}"
        )
    else:
        st.warning("No data — load via **Admin** tab")

# ---------------------------------------------------------------------------
# Tabs
# Tab list is built dynamically so feature-flagged tabs can be fully absent
# from the UI (not just empty). To add a tab: see CLAUDE.md → "Adding a new tab".
# ---------------------------------------------------------------------------
from config.defaults import ENABLE_LONG_TERM_VIEW
from tabs import tab_short_term, tab_long_term, tab_scenario_planner, tab_admin, tab_help

_tab_labels = ["📅 Short-Term View"]
if ENABLE_LONG_TERM_VIEW:
    _tab_labels.append("📈 Long-Term View")
_tab_labels += ["🔀 Scenario Planner", "⚙️ Admin", "📖 Help"]

_tabs = st.tabs(_tab_labels)
_idx = 0

# Unpack tab handles in order, skipping flagged tabs that aren't in the list
_t_short = _tabs[_idx]; _idx += 1
_t_long  = _tabs[_idx] if ENABLE_LONG_TERM_VIEW else None; _idx += (1 if ENABLE_LONG_TERM_VIEW else 0)
_t_scenario, _t_admin, _t_help = _tabs[_idx], _tabs[_idx + 1], _tabs[_idx + 2]

with _t_short:
    tab_short_term.render()

if ENABLE_LONG_TERM_VIEW:
    with _t_long:
        tab_long_term.render()

with _t_scenario:
    tab_scenario_planner.render()

with _t_admin:
    tab_admin.render()

with _t_help:
    tab_help.render()
