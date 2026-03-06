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
    fig.update_layout(
        height=max(300, len(df) * 35),
        yaxis_type="category",
        coloraxis_colorbar=dict(title="Utilization %", tickformat=".0%"),
    )
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
        zmin=0,
        text=matrix,
        texttemplate="%{text}",
        hovertemplate="Floor: %{y}<br>Unit: %{x}<br>Seats: %{z}<extra></extra>",
        colorbar=dict(title="Seats"),
    ))
    fig.update_layout(
        title="Unit Seat Distribution by Floor",
        xaxis_title="Unit",
        yaxis_title="Floor",
        height=max(400, len(floors) * 30),
    )
    return fig


def rto_need_vs_allocated_bar(rto_data: List[dict]) -> go.Figure:
    """Grouped bar chart comparing RTO-based need vs allocated seats per unit."""
    df = pd.DataFrame(rto_data)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Allocated",
        x=df["unit_name"],
        y=df["allocated_seats"],
        marker_color="#4A90D9",
    ))
    fig.add_trace(go.Bar(
        name="RTO Need",
        x=df["unit_name"],
        y=df["expected_seats"],
        marker_color="#E8734A",
    ))
    fig.update_layout(
        barmode="group",
        title="Allocated Seats vs RTO-Based Need by Unit",
        xaxis_title="Unit",
        yaxis_title="Seats",
        height=400,
        legend_title_text="",
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


def tornado_chart(
    sensitivity_data: List[dict],
    title: str = "Sensitivity Analysis — Impact on Total Seat Gap",
) -> go.Figure:
    """Horizontal tornado chart showing parameter sensitivity ranked by impact."""
    df = pd.DataFrame(sensitivity_data)
    df = df.nlargest(12, "abs_delta")
    df["label"] = df["parameter"] + " (" + df["variation_label"] + ")"
    df = df.sort_values("abs_delta", ascending=True)

    colors_list = ["#CC0000" if d < 0 else "#006400" for d in df["gap_delta"]]

    fig = go.Figure(go.Bar(
        x=df["gap_delta"],
        y=df["label"],
        orientation="h",
        marker_color=colors_list,
        text=[f"{d:+d}" for d in df["gap_delta"]],
        textposition="auto",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Change in Total Seat Gap (seats)",
        yaxis_title="",
        height=max(350, len(df) * 35),
        showlegend=False,
    )
    fig.add_vline(x=0, line_dash="dash", line_color="grey")
    return fig


def colocation_heatmap(
    scores: List[dict],
    title: str = "Unit Co-location Affinity",
) -> go.Figure:
    """Heatmap of pairwise co-location scores (top pairs only)."""
    if not scores:
        return go.Figure()

    unit_set = set()
    for s in scores:
        unit_set.add(s["unit_a"])
        unit_set.add(s["unit_b"])
    unit_list = sorted(unit_set)

    n = len(unit_list)
    idx = {name: i for i, name in enumerate(unit_list)}
    matrix = [[0.0] * n for _ in range(n)]
    for s in scores:
        i, j = idx[s["unit_a"]], idx[s["unit_b"]]
        matrix[i][j] = s["score"]
        matrix[j][i] = s["score"]
    for i in range(n):
        matrix[i][i] = 1.0

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=unit_list,
        y=unit_list,
        colorscale="Greens",
        zmin=0, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in matrix],
        texttemplate="%{text}",
        hovertemplate="Unit A: %{y}<br>Unit B: %{x}<br>Score: %{z:.2f}<extra></extra>",
        colorbar=dict(title="Score"),
    ))
    fig.update_layout(
        title=title,
        height=max(400, n * 50),
        xaxis_title="Unit",
        yaxis_title="Unit",
    )
    return fig


# ── Forecasting Charts ───────────────────────────────────────────────────

def attendance_trend_chart(
    historical_dates, historical_values,
    ema_values,
    forecast_dates, forecast_median, forecast_upper, forecast_lower,
    unit_name: str,
) -> go.Figure:
    """Line chart with historical scatter, EMA, and forecast with CI bands."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=historical_dates, y=historical_values,
        mode="markers", name="Actual",
        marker=dict(size=3, color="#4A90D9", opacity=0.5),
    ))

    fig.add_trace(go.Scatter(
        x=historical_dates, y=ema_values,
        mode="lines", name="EMA (21-day)",
        line=dict(color="#4A90D9", width=2),
    ))

    fig.add_trace(go.Scatter(
        x=forecast_dates, y=forecast_median,
        mode="lines", name="Forecast",
        line=dict(color="#E8734A", width=2, dash="dash"),
    ))

    fig.add_trace(go.Scatter(
        x=list(forecast_dates) + list(forecast_dates[::-1]),
        y=list(forecast_upper) + list(forecast_lower[::-1]),
        fill="toself", fillcolor="rgba(232,115,74,0.15)",
        line=dict(width=0), name="95% CI",
    ))

    fig.update_layout(
        title=f"Attendance Trend & Forecast — {unit_name}",
        xaxis_title="Date", yaxis_title="In-Office Count",
        height=400, hovermode="x unified",
    )
    return fig


def dow_heatmap_chart(
    dow_df: pd.DataFrame,
    title: str = "Day-of-Week Attendance Patterns",
) -> go.Figure:
    """Heatmap: units (y) x day-of-week (x), colored by median attendance."""
    pivot = dow_df.pivot_table(
        index="unit_name", columns="day_name", values="median_count",
    )
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    pivot = pivot[[d for d in day_order if d in pivot.columns]]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="YlOrRd",
        text=[[f"{v:.0f}" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        hovertemplate="Unit: %{y}<br>Day: %{x}<br>Median: %{z:.0f}<extra></extra>",
        colorbar=dict(title="Median"),
    ))
    fig.update_layout(title=title, height=max(300, len(pivot) * 45))
    return fig


def probabilistic_demand_bar(
    demand_data: List[dict],
    selected_confidence: float = 0.95,
) -> go.Figure:
    """Grouped bar: peak vs percentile-based demand per unit."""
    units = [d["unit_name"] for d in demand_data]
    peaks = [d["peak"] for d in demand_data]
    percentile_vals = [d["percentiles"][selected_confidence] for d in demand_data]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Peak-Based", x=units, y=peaks, marker_color="#E8734A"))
    fig.add_trace(go.Bar(
        name=f"{selected_confidence:.0%} Percentile",
        x=units, y=percentile_vals, marker_color="#4A90D9",
    ))

    fig.update_layout(
        barmode="group",
        title=f"Peak vs {selected_confidence:.0%} Percentile Demand",
        xaxis_title="Unit", yaxis_title="Seats Needed",
        height=400,
    )
    return fig


def correlation_heatmap_chart(corr_df: pd.DataFrame) -> go.Figure:
    """Heatmap of pairwise demand correlation between units."""
    fig = go.Figure(data=go.Heatmap(
        z=corr_df.values,
        x=corr_df.columns.tolist(),
        y=corr_df.index.tolist(),
        colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr_df.values],
        texttemplate="%{text}",
        colorbar=dict(title="Correlation"),
    ))
    fig.update_layout(
        title="Demand Correlation Between Units",
        height=max(400, len(corr_df) * 50),
    )
    return fig
