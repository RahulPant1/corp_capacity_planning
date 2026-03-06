"""Multi-scenario comparison charts for the Scenario Comparison Matrix."""

from typing import List
import plotly.graph_objects as go
import plotly.express as px
import numpy as np


def scenario_label(r: dict) -> str:
    """Short display label for a scenario result."""
    parts = []
    if r.get("alloc_pct") is not None:
        parts.append(f"A{r['alloc_pct']:.0%}")
    parts.append(f"R{r['rto_mandate']:.1f}")
    if r.get("cap_red", 0) > 0:
        parts.append(f"C{r['cap_red']:.0%}")
    obj_short = {"optimal_placement": "Opt", "rto_based": "RTO", "rto_whatif": "WI"}.get(
        r["objective"], r["objective"]
    )
    parts.append(obj_short)
    return f"#{r['rank']} " + " ".join(parts)


def scenario_demand_capacity_bar(results: List[dict]) -> go.Figure:
    """Grouped bar chart: Demand vs Capacity vs Optimized Seats per scenario.

    Each scenario is a group of 3 bars: Demand, Capacity, Optimized Seats.
    """
    labels   = [scenario_label(r) for r in results]
    demand   = [r["demand"]    for r in results]
    capacity = [r["capacity"]  for r in results]
    opt_seats = [r["opt_seats"] for r in results]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Demand",
        x=labels, y=demand,
        marker_color="steelblue",
        hovertemplate="%{x}<br>Demand: %{y:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Capacity",
        x=labels, y=capacity,
        marker_color="lightgreen",
        hovertemplate="%{x}<br>Capacity: %{y:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Optimized Seats",
        x=labels, y=opt_seats,
        marker_color="coral",
        hovertemplate="%{x}<br>Optimized: %{y:,}<extra></extra>",
    ))

    fig.update_layout(
        barmode="group",
        title="Demand vs Capacity vs Optimized Seats",
        xaxis_title="Scenario",
        yaxis_title="Seats",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380,
        margin=dict(t=60, b=60),
    )
    return fig


def scenario_metrics_heatmap(results: List[dict]) -> go.Figure:
    """Normalized metrics heatmap: scenarios (rows) × KPIs (columns).

    Each cell shows the normalized score (0-1, higher = better).
    Colour scale: RdYlGn (red = bad, green = good).
    """
    metric_configs = [
        ("Headroom",       "headroom",         True,  False),  # (label, key, higher_better, is_abs)
        ("Total Gap",      "total_gap",         True,  False),
        ("Units at Risk",  "units_at_risk",     False, False),
        ("Opt Seats",      "opt_seats",         False, False),
        ("Floors Used",    "floors_used",       False, False),
        ("Avg Frag",       "avg_fragmentation", False, False),
        ("Score",          "composite_score",   True,  False),
    ]

    labels = [scenario_label(r) for r in results]
    metric_names = [m[0] for m in metric_configs]

    # Build raw value matrix
    raw = np.zeros((len(results), len(metric_configs)))
    for j, (_, key, _, _) in enumerate(metric_configs):
        vals = np.array([float(r.get(key, 0) or 0) for r in results], dtype=float)
        raw[:, j] = vals

    # Normalize each column 0-1 respecting higher_better
    norm = np.zeros_like(raw)
    for j, (_, _, higher_better, _) in enumerate(metric_configs):
        col = raw[:, j]
        mn, mx = col.min(), col.max()
        if mx == mn:
            norm[:, j] = 1.0
        else:
            n = (col - mn) / (mx - mn)
            norm[:, j] = n if higher_better else 1.0 - n

    # Hover text: raw values
    hover = []
    for i, r in enumerate(results):
        row = []
        for j, (_, key, _, _) in enumerate(metric_configs):
            val = r.get(key, 0)
            if isinstance(val, float) and val < 10:
                row.append(f"{val:.3f}")
            else:
                row.append(f"{val:,}" if isinstance(val, (int, float)) else str(val))
        hover.append(row)

    fig = go.Figure(go.Heatmap(
        z=norm,
        x=metric_names,
        y=labels,
        colorscale="RdYlGn",
        zmin=0, zmax=1,
        text=hover,
        texttemplate="%{text}",
        hovertemplate="Scenario: %{y}<br>Metric: %{x}<br>Value: %{text}<extra></extra>",
        showscale=True,
        colorbar=dict(title="Score<br>(0=worst,<br>1=best)", len=0.8),
    ))

    fig.update_layout(
        title="Scenario Metrics Comparison (normalized, green = better)",
        xaxis=dict(side="top"),
        height=max(300, 50 + 40 * len(results)),
        margin=dict(t=100, b=40, l=140, r=80),
    )
    return fig
