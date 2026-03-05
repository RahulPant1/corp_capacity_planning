"""Floor Map visualization — treemap-style block diagrams showing unit allocations per floor."""

import plotly.graph_objects as go
from typing import List, Optional, Dict

# Fixed color palette for consistent unit coloring across views
UNIT_COLORS = [
    "#4A90D9", "#E8734A", "#50B878", "#F5C542", "#9B59B6",
    "#1ABC9C", "#E74C3C", "#3498DB", "#F39C12", "#8E44AD",
    "#2ECC71", "#E67E22", "#16A085", "#C0392B", "#2980B9",
]


def _get_unit_color_map(unit_names: List[str]) -> Dict[str, str]:
    """Return a consistent color mapping for unit names."""
    sorted_names = sorted(set(unit_names))
    return {name: UNIT_COLORS[i % len(UNIT_COLORS)] for i, name in enumerate(sorted_names)}


def render_floor_map(
    assignments: list,
    total_seats: int,
    floor_label: str,
    unit_color_map: Optional[Dict[str, str]] = None,
    height: int = 220,
) -> go.Figure:
    """Render a treemap-style floor map for a single floor.

    Args:
        assignments: list of dicts with 'unit_name' and 'seats_assigned'
        total_seats: total seat capacity on this floor
        floor_label: display label (e.g., 'B1-T1-F3')
        unit_color_map: optional pre-built color map for consistency
        height: figure height in pixels

    Returns:
        Plotly Figure with treemap
    """
    labels = []
    values = []
    colors = []
    hover_texts = []

    if unit_color_map is None:
        unit_color_map = _get_unit_color_map([a["unit_name"] for a in assignments])

    used_seats = 0
    for a in sorted(assignments, key=lambda x: -x["seats_assigned"]):
        name = a["unit_name"]
        seats = a["seats_assigned"]
        if seats <= 0:
            continue
        labels.append(name)
        values.append(seats)
        colors.append(unit_color_map.get(name, "#888888"))
        pct = seats / total_seats * 100 if total_seats > 0 else 0
        hover_texts.append(f"{name}<br>{seats} seats ({pct:.0f}%)")
        used_seats += seats

    # Available (unassigned) block
    available = total_seats - used_seats
    if available > 0:
        labels.append("Available")
        values.append(available)
        colors.append("#E0E0E0")
        pct = available / total_seats * 100 if total_seats > 0 else 0
        hover_texts.append(f"Available<br>{available} seats ({pct:.0f}%)")

    fig = go.Figure(go.Treemap(
        labels=labels,
        values=values,
        parents=[""] * len(labels),
        marker=dict(colors=colors, line=dict(width=2, color="white")),
        textinfo="label+value",
        textfont=dict(size=12),
        hovertext=hover_texts,
        hoverinfo="text",
    ))
    fig.update_layout(
        title=dict(text=floor_label, font=dict(size=13)),
        margin=dict(l=5, r=5, t=30, b=5),
        height=height,
    )
    return fig


def render_floor_map_grid(
    floor_assignments_by_floor: Dict[str, dict],
    columns: int = 2,
):
    """Render a grid of floor maps using Streamlit columns.

    Args:
        floor_assignments_by_floor: dict mapping floor_id to
            {'total_seats': int, 'assignments': [{'unit_name': str, 'seats_assigned': int}]}
        columns: number of columns in the grid
    """
    import streamlit as st

    # Build global color map for consistency
    all_units = set()
    for fdata in floor_assignments_by_floor.values():
        for a in fdata["assignments"]:
            all_units.add(a["unit_name"])
    color_map = _get_unit_color_map(list(all_units))

    floor_ids = sorted(floor_assignments_by_floor.keys())
    for i in range(0, len(floor_ids), columns):
        cols = st.columns(columns)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(floor_ids):
                break
            fid = floor_ids[idx]
            fdata = floor_assignments_by_floor[fid]
            fig = render_floor_map(
                assignments=fdata["assignments"],
                total_seats=fdata["total_seats"],
                floor_label=fid,
                unit_color_map=color_map,
            )
            with col:
                st.plotly_chart(fig, use_container_width=True, key=f"floormap_{fid}")
