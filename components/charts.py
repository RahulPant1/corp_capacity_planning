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


def temporal_cluster_dow_chart(
    cluster_data: List[dict],
    dow_df: pd.DataFrame,
) -> go.Figure:
    """Grouped bar chart: average Mon–Fri attendance profile per temporal cluster.

    Args:
        cluster_data: list of dicts with keys unit_name, cluster_label
        dow_df: output of compute_dow_patterns() — unit_name, day_name, median_count
    """
    palette = ["#4A90D9", "#E8734A", "#2ECC71", "#9B59B6", "#F39C12", "#1ABC9C"]
    cluster_map = {row["unit_name"]: row["cluster_label"] for row in cluster_data}

    work = dow_df.copy()
    work["cluster"] = work["unit_name"].map(cluster_map)
    work = work.dropna(subset=["cluster"])
    if work.empty:
        return go.Figure()

    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    work["day_name"] = pd.Categorical(work["day_name"], categories=day_order, ordered=True)
    agg = (
        work.groupby(["cluster", "day_name"], observed=True)["median_count"]
        .mean()
        .reset_index()
        .sort_values(["cluster", "day_name"])
    )

    clusters = sorted(agg["cluster"].unique())
    fig = go.Figure()
    for i, cluster in enumerate(clusters):
        cdf = agg[agg["cluster"] == cluster]
        fig.add_trace(go.Bar(
            name=cluster,
            x=cdf["day_name"],
            y=cdf["median_count"],
            marker_color=palette[i % len(palette)],
            text=[f"{v:.0f}" for v in cdf["median_count"]],
            textposition="outside",
        ))

    fig.update_layout(
        barmode="group",
        title="Average Attendance Profile by Cluster Group (Mon–Fri)",
        xaxis_title="Day of Week",
        yaxis_title="Avg In-Office Count",
        height=380,
        legend_title_text="Cluster",
    )
    return fig


def correlation_heatmap_chart(corr_df: pd.DataFrame) -> go.Figure:
    """Upper-triangle heatmap of pairwise demand correlation between units.

    Lower triangle is masked to reduce visual clutter.
    Red = high positive (units peak together). Blue = negative (complementary).
    """
    import numpy as np

    labels = corr_df.columns.tolist()
    n = len(labels)
    values = corr_df.values.astype(float)

    # Mask lower triangle — show diagonal + upper only
    masked = np.where(np.tril(np.ones((n, n)), k=-1).astype(bool), None, values)
    text = [
        [f"{values[i][j]:.2f}" if j >= i else "" for j in range(n)]
        for i in range(n)
    ]

    fig = go.Figure(data=go.Heatmap(
        z=masked,
        x=labels,
        y=labels,
        colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1,
        text=text,
        texttemplate="%{text}",
        hovertemplate="Unit A: %{y}<br>Unit B: %{x}<br>Correlation: %{z:.2f}<extra></extra>",
        colorbar=dict(title="Correlation<br>(-1 to +1)"),
        showscale=True,
    ))
    fig.update_layout(
        title="Demand Correlation (upper triangle)",
        height=max(320, n * 46),
        margin=dict(t=50, b=20),
        yaxis=dict(autorange="reversed"),
    )
    return fig
