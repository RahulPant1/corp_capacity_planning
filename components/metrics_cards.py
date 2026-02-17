"""Reusable KPI metric card widgets."""

import streamlit as st


def render_metric_row(metrics: list[dict]):
    """Render a row of metric cards.

    Each metric dict should have: label, value, and optionally delta, delta_color.
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            delta = m.get("delta")
            delta_color = m.get("delta_color", "normal")
            st.metric(
                label=m["label"],
                value=m["value"],
                delta=delta,
                delta_color=delta_color,
            )


def render_alert_card(message: str, level: str = "warning"):
    """Render an alert card with appropriate styling."""
    if level == "error":
        st.error(message, icon="🔴")
    elif level == "warning":
        st.warning(message, icon="🟡")
    else:
        st.info(message, icon="🔵")
