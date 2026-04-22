"""Long-Term View tab — currently disabled.

Controlled by ENABLE_LONG_TERM_VIEW in config/defaults.py (default: False).
When False, this tab is not added to the st.tabs() list in app.py at all.

To re-enable: set ENABLE_LONG_TERM_VIEW = True in config/defaults.py.
The tab will appear automatically — no other changes needed.

When re-enabling, implement a new render() body that reads from ci_daily_df.
The old implementation (removed during cleanup) required engine functions
compute_long_term_kpis, compute_city_capacity_metrics, generate_insights_long_term
which were never built — they need to be added to engine/capacity_forecast.py first.
"""


def render() -> None:
    import streamlit as st

    st.info(
        "**Long-Term View is not available in this version.**\n\n"
        "The prediction file covers a maximum 60-day horizon. "
        "Long-term (6–12 month) views will be enabled once a longer-range model output is available.",
        icon="📅",
    )
