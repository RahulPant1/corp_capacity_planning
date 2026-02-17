"""Plotly chart builders for the CPG Seat Planning Platform."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict


def capacity_vs_demand_bar(
    buildings: List[dict],
    title: str = "Capacity vs Demand by Tower",
) -> go.Figure:
    """Bar chart comparing total capacity and demand by tower."""
    df = pd.DataFrame(buildings)
    fig = px.bar(
        df, x="tower_id", y=["total_seats", "used_seats"],
        barmode="group",
        labels={"value": "Seats", "tower_id": "Tower", "variable": ""},
        title=title,
        color_discrete_map={"total_seats": "#4A90D9", "used_seats": "#E8734A"},
    )
    fig.update_layout(legend_title_text="", height=400)
    return fig


def utilization_donut(used: int, total: int, title: str = "Overall Utilization") -> go.Figure:
    """Donut chart showing overall seat utilization."""
    available = total - used
    fig = go.Figure(data=[go.Pie(
        labels=["Used", "Available"],
        values=[used, available],
        hole=0.6,
        marker_colors=["#E8734A", "#4A90D9"],
        textinfo="percent+label",
    )])
    fig.update_layout(
        title=title,
        height=350,
        showlegend=True,
        annotations=[dict(text=f"{used}/{total}", x=0.5, y=0.5, font_size=16, showarrow=False)],
    )
    return fig


def floor_heatmap(
    utilization_data: List[dict],
    tower_filter: str = None,
) -> go.Figure:
    """Heatmap of floor utilization by tower."""
    df = pd.DataFrame(utilization_data)
    if tower_filter:
        df = df[df["tower_id"] == tower_filter]

    df = df.sort_values("floor_number", ascending=False)

    fig = px.bar(
        df, x="utilization_pct", y=df["floor_id"],
        orientation="h",
        title=f"Floor Utilization{' — ' + tower_filter if tower_filter else ''}",
        labels={"utilization_pct": "Utilization %", "y": "Floor"},
        color="utilization_pct",
        color_continuous_scale=["#4A90D9", "#F5C542", "#E8734A"],
        range_color=[0, 1],
    )
    fig.update_layout(height=max(300, len(df) * 35), yaxis_type="category")
    fig.update_traces(texttemplate="%{x:.0%}", textposition="auto")
    return fig


def unit_floor_heatmap(
    assignments: List[dict],
    floors: List[str],
    units: List[str],
) -> go.Figure:
    """Heatmap showing seats per unit per floor."""
    # Build matrix
    data = {}
    for a in assignments:
        fid = f"{a['tower_id']}-F{a['floor_number']}"
        if fid not in data:
            data[fid] = {}
        data[fid][a["unit_name"]] = data[fid].get(a["unit_name"], 0) + a["seats_assigned"]

    matrix = []
    for fid in sorted(floors, reverse=True):
        row = [data.get(fid, {}).get(u, 0) for u in units]
        matrix.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=units,
        y=sorted(floors, reverse=True),
        colorscale="YlOrRd",
        text=matrix,
        texttemplate="%{text}",
        hovertemplate="Floor: %{y}<br>Unit: %{x}<br>Seats: %{z}<extra></extra>",
    ))
    fig.update_layout(
        title="Unit Seat Distribution by Floor",
        xaxis_title="Unit",
        yaxis_title="Floor",
        height=max(400, len(floors) * 30),
    )
    return fig


def scenario_comparison_bar(comparison_df: pd.DataFrame) -> go.Figure:
    """Bar chart comparing seat allocations across two scenarios."""
    fig = go.Figure()

    cols = [c for c in comparison_df.columns if "Seats" in c and "Change" not in c]
    colors = ["#4A90D9", "#E8734A"]

    for i, col in enumerate(cols[:2]):
        fig.add_trace(go.Bar(
            name=col,
            x=comparison_df["Unit"],
            y=comparison_df[col],
            marker_color=colors[i % 2],
        ))

    fig.update_layout(
        barmode="group",
        title="Scenario Seat Comparison",
        xaxis_title="Unit",
        yaxis_title="Seats",
        height=400,
    )
    return fig
