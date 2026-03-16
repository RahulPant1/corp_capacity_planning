"""Styled dataframe display helpers."""

import streamlit as st
import pandas as pd
from typing import Optional


def render_styled_table(
    df: pd.DataFrame,
    title: Optional[str] = None,
    height: Optional[int] = None,
    use_container_width: bool = True,
):
    """Render a styled, non-editable dataframe."""
    if title:
        st.subheader(title)
    st.dataframe(df, height=height, use_container_width=use_container_width)


def render_risk_table(df: pd.DataFrame, risk_column: str = "Risk Level"):
    """Render a table with color-coded risk levels."""
    def color_risk(val):
        if val == "RED":
            return "background-color: #ffcccc; color: #cc0000; font-weight: bold"
        elif val == "AMBER":
            return "background-color: #fff3cd; color: #856404; font-weight: bold"
        elif val == "GREEN":
            return "background-color: #d4edda; color: #155724; font-weight: bold"
        return ""

    if risk_column in df.columns:
        styled = df.style.map(color_risk, subset=[risk_column])
        st.dataframe(styled, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)


def render_comparison_table(df: pd.DataFrame, change_column: str = "Seat Change"):
    """Render a comparison table with positive/negative highlighting."""
    def color_change(val):
        try:
            v = float(val)
            if v > 0:
                return "color: #155724; font-weight: bold"
            elif v < 0:
                return "color: #cc0000; font-weight: bold"
        except (ValueError, TypeError):
            pass
        return ""

    if change_column in df.columns:
        styled = df.style.map(color_change, subset=[change_column])
        st.dataframe(styled, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)
