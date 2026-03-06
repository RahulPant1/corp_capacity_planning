"""Tab 7: Demand Forecasting — trend analysis, probabilistic demand, growth suggestions."""

import streamlit as st
import pandas as pd
import numpy as np

from data.session_store import (
    is_data_loaded, get_units, get_attendance,
    get_daily_attendance_df, set_daily_attendance,
    get_active_scenario, update_scenario,
    add_audit_entry,
)
from data.loader import load_file, parse_daily_attendance
from data.validator import validate_daily_attendance, validate_daily_attendance_cross
from engine.forecasting import (
    compute_unit_trend, compute_overall_trend, compute_dow_patterns,
    compute_percentile_demand, bootstrap_confidence_interval,
    compute_forecast_summary, compute_demand_correlation,
    compute_capacity_breach_probability, compute_temporal_clustering,
)
from components.charts import (
    attendance_trend_chart, dow_heatmap_chart,
    probabilistic_demand_bar, correlation_heatmap_chart,
)
from models.scenario import ScenarioOverride
from config.defaults import FORECAST_CONFIDENCE_LEVELS, FORECAST_DEFAULT_MONTHS


def render(sidebar_state):
    """Render the Demand Forecasting tab."""
    st.header("Demand Forecasting")

    with st.expander("How does forecasting work?", expanded=False):
        st.markdown("""
**Input:** Daily attendance data (CSV with Date, Unit Name, In-Office Count).

**Features:**
- **Trend Analysis** — Linear regression + EMA on daily data → forecasted median/peak + suggested growth %
- **Probabilistic Demand** — Instead of using peak attendance, compute 90th/95th/99th percentile → potential seat savings
- **Day-of-Week Patterns** — Heatmap showing which days each unit is busiest (e.g., Tue/Wed peak)
- **Demand Correlation** — Which units' attendance moves together (compete for seats on same days)
- **Capacity Breach Risk** — Probability that daily attendance exceeds allocated seats
- **Temporal Clusters** — Groups units by similar attendance behavior for hot-desking opportunities

**Integration:** Click *Apply Forecasted Growth* to push data-driven growth % into Scenario Lab.
        """)

    daily_df = get_daily_attendance_df()

    # ── Section 1: Data Upload ─────────────────────────────────────────────
    with st.expander(
        "Upload Daily Attendance Data" if daily_df is None
        else f"Daily Attendance Data ({len(daily_df):,} records loaded)",
        expanded=(daily_df is None),
    ):
        st.caption(
            "Upload a CSV with columns: **Date**, **Unit Name**, **In-Office Count**. "
            "One row per unit per day. Minimum 30 days recommended."
        )

        uploaded = st.file_uploader(
            "Daily Attendance CSV", type=["csv", "xlsx"],
            key="upload_daily_attendance",
        )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Upload & Validate", type="primary", key="btn_upload_daily"):
                if uploaded:
                    try:
                        raw_df = load_file(uploaded)
                        result = validate_daily_attendance(raw_df)
                        for e in result.errors:
                            st.error(e)
                        for w in result.warnings:
                            st.warning(w)
                        if result.is_valid:
                            records = parse_daily_attendance(raw_df)
                            df = pd.DataFrame([
                                {"date": r.date, "unit_name": r.unit_name,
                                 "in_office_count": r.in_office_count}
                                for r in records
                            ])
                            df["date"] = pd.to_datetime(df["date"])
                            set_daily_attendance(records, df)

                            if is_data_loaded():
                                units = get_units()
                                units_df = pd.DataFrame([{"Unit Name": u.unit_name} for u in units])
                                cross = validate_daily_attendance_cross(raw_df, units_df)
                                for w in cross.warnings:
                                    st.warning(w)

                            st.success(
                                f"Loaded {len(records):,} records for "
                                f"{df['unit_name'].nunique()} units "
                                f"({df['date'].min().date()} to {df['date'].max().date()})."
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error loading file: {e}")
                else:
                    st.warning("Please upload a file first.")

        with btn_col2:
            if st.button("Generate Sample Data", key="btn_sample_daily",
                         help="Creates 90 days of synthetic daily attendance for demo purposes."):
                from data.sample_data import generate_daily_attendance_df
                sample_df = generate_daily_attendance_df()
                records = parse_daily_attendance(sample_df)
                df = pd.DataFrame([
                    {"date": r.date, "unit_name": r.unit_name,
                     "in_office_count": r.in_office_count}
                    for r in records
                ])
                df["date"] = pd.to_datetime(df["date"])
                set_daily_attendance(records, df)
                st.success(
                    f"Generated {len(records):,} sample records for "
                    f"{df['unit_name'].nunique()} units."
                )
                st.rerun()

        if daily_df is not None:
            st.caption(
                f"Date range: {daily_df['date'].min().date()} to "
                f"{daily_df['date'].max().date()} | "
                f"Units: {daily_df['unit_name'].nunique()} | "
                f"Records: {len(daily_df):,}"
            )

    # Guard: need daily data for everything below
    if daily_df is None:
        st.info("Upload daily attendance data above to enable forecasting features.")
        return

    unit_names = sorted(daily_df["unit_name"].unique())
    unit_options = ["All Units (Overall)"] + list(unit_names)

    # ── Section 2: Trend Analysis ──────────────────────────────────────────
    st.divider()
    st.subheader("Attendance Trends & Forecast")

    t_col1, t_col2 = st.columns([2, 1])
    with t_col1:
        selected_unit = st.selectbox(
            "Select Unit", unit_options, index=0, key="forecast_unit_select",
        )
    with t_col2:
        forecast_months = st.slider(
            "Forecast Horizon (months)", 1, 12, FORECAST_DEFAULT_MONTHS,
            key="forecast_horizon_slider",
        )

    # Compute trend (overall aggregate or per-unit)
    if selected_unit == "All Units (Overall)":
        trend = compute_overall_trend(daily_df, forecast_months)
        chart_label = "All Units (Total)"
    else:
        trend = compute_unit_trend(daily_df, selected_unit, forecast_months)
        chart_label = selected_unit

    if trend:
        fig = attendance_trend_chart(
            trend["historical_dates"], trend["historical_values"],
            trend["ema_values"],
            trend["forecast_dates"], trend["forecast_median"],
            trend["forecast_upper"], trend["forecast_lower"],
            chart_label,
        )
        st.plotly_chart(fig, use_container_width=True, key="forecast_trend_chart")

        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("Current Median", f"{trend['current_median']:.0f}")
        tc2.metric("Trend Slope", f"{trend['trend_slope']:.2f}/day")
        tc3.metric("Residual Std", f"±{trend['residual_std']:.1f}")
        tc4.metric("Suggested Growth %", f"{trend['suggested_growth_pct']:.1%}")
    else:
        st.warning(f"Insufficient data for {selected_unit} (need at least 7 days).")

    # Methodology explanation
    with st.expander("How is this forecast projected?", expanded=False):
        st.markdown("""
**Methodology:**

1. **Historical data** (light blue dots) — your raw daily in-office attendance counts.

2. **EMA line** (solid blue) — a 21-day Exponential Moving Average that smooths out daily noise
   to reveal the underlying attendance trend. Recent days are weighted more heavily than older ones.

3. **Trend line & forecast** (dashed orange) — a linear regression (best-fit straight line) through
   all historical data points, projected forward by the selected number of months.
   - The **slope** tells you how many people per day the attendance is changing
   - A positive slope means attendance is growing; negative means declining

4. **95% confidence band** (shaded orange) — based on the standard deviation of residuals
   (how much actual data deviates from the trend line). There is a 95% probability that
   future attendance will fall within this band, assuming the trend continues.

5. **Suggested Growth %** — the trend slope annualized relative to the current median:
   `(slope / current_median) × 365`. This can be applied directly to the Scenario Lab
   growth forecast to replace manual estimates with data-driven projections.

**Limitations:** Linear trend assumes constant growth rate. Seasonal patterns (e.g., holiday dips)
or structural changes (e.g., new RTO policy) may cause the actual trajectory to deviate.
        """)

    # ── Section 3: Forecast Summary ────────────────────────────────────────
    st.divider()
    st.subheader("Forecast Summary (All Units)")

    summaries = compute_forecast_summary(daily_df, unit_names, forecast_months)
    if summaries:
        summary_df = pd.DataFrame(summaries)
        display_df = summary_df.copy()
        display_df["suggested_growth_pct"] = display_df["suggested_growth_pct"].apply(
            lambda x: f"{x:.1%}"
        )
        display_df.columns = [
            "Unit", "Current Median", "Current Peak",
            f"Forecasted Median ({forecast_months}m)",
            f"Forecasted Peak ({forecast_months}m)",
            "Suggested Growth %",
        ]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Apply button
        if is_data_loaded():
            if st.button(
                "Apply Forecasted Growth to Active Scenario",
                type="primary", key="btn_apply_growth",
            ):
                scenario = get_active_scenario()
                if scenario and not scenario.is_locked:
                    for s in summaries:
                        override = scenario.unit_overrides.get(
                            s["unit_name"],
                            ScenarioOverride(unit_name=s["unit_name"]),
                        )
                        override.hc_growth_pct = s["suggested_growth_pct"]
                        scenario.unit_overrides[s["unit_name"]] = override
                    update_scenario(scenario)
                    add_audit_entry(
                        "forecast_apply", scenario.scenario_id,
                        "hc_growth_pct", "manual", "forecasted",
                        rationale=f"Applied {len(summaries)} data-driven growth forecasts",
                    )
                    st.success(
                        f"Applied forecasted growth to {len(summaries)} units "
                        f"in scenario '{scenario.name}'. "
                        f"Re-run simulation in Scenario Lab to see updated demand."
                    )
                elif scenario and scenario.is_locked:
                    st.warning("Active scenario is locked. Unlock it first.")
                else:
                    st.warning("No active scenario found.")

    # ── Section 4: Probabilistic Demand ────────────────────────────────────
    st.divider()
    st.subheader("Probabilistic Seat Demand")
    st.caption(
        "Instead of allocating for peak attendance, compute the seats needed at a given "
        "confidence level. Lower confidence = fewer seats but more risk of exceeding capacity."
    )

    confidence = st.select_slider(
        "Confidence Level",
        options=FORECAST_CONFIDENCE_LEVELS,
        value=0.95,
        format_func=lambda x: f"{x:.0%}",
        key="confidence_slider",
    )

    demand_data = []
    for name in unit_names:
        result = compute_percentile_demand(daily_df, name)
        if result:
            demand_data.append(result)

    if demand_data:
        fig = probabilistic_demand_bar(demand_data, confidence)
        st.plotly_chart(fig, use_container_width=True, key="prob_demand_chart")

        total_peak = sum(d["peak"] for d in demand_data)
        total_percentile = sum(d["percentiles"][confidence] for d in demand_data)
        total_savings = total_peak - total_percentile

        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Total Peak-Based Demand", f"{total_peak:,}")
        pc2.metric(f"Total {confidence:.0%} Demand", f"{total_percentile:,}")
        pc3.metric("Potential Savings", f"{total_savings:,} seats",
                   delta=f"-{total_savings}", delta_color="inverse")

        # Detail table with bootstrap CI
        detail_rows = []
        for d in demand_data:
            bs = bootstrap_confidence_interval(daily_df, d["unit_name"], confidence)
            detail_rows.append({
                "Unit": d["unit_name"],
                "Median": d["median"],
                "Peak": d["peak"],
                f"{confidence:.0%} Percentile": d["percentiles"][confidence],
                "Savings vs Peak": d["savings_vs_peak"][confidence],
                "Bootstrap CI": f"[{bs['ci_lower']}, {bs['ci_upper']}]" if bs else "N/A",
                "Observations": d["n_observations"],
            })
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

    # ── Section 5: Day-of-Week Patterns ────────────────────────────────────
    st.divider()
    st.subheader("Day-of-Week Attendance Patterns")

    dow_df = compute_dow_patterns(daily_df)
    if not dow_df.empty:
        fig = dow_heatmap_chart(dow_df)
        st.plotly_chart(fig, use_container_width=True, key="dow_heatmap_chart")
        st.caption(
            "Median in-office count by day of week. Use this to identify peak days "
            "(e.g., Tue/Wed) and low-attendance days suitable for hot-desking policies."
        )

    # ── Section 6: Advanced Insights ──────────────────────────────────────
    st.divider()
    st.subheader("Advanced Insights")

    adv_tab1, adv_tab2, adv_tab3 = st.tabs([
        "Demand Correlation", "Capacity Breach Risk", "Temporal Clusters",
    ])

    with adv_tab1:
        st.caption(
            "Pearson correlation of daily attendance between units. "
            "High positive = units peak together (compete for seats). "
            "Negative = opportunity for desk sharing."
        )
        corr_df = compute_demand_correlation(daily_df, unit_names)
        if not corr_df.empty:
            fig = correlation_heatmap_chart(corr_df)
            st.plotly_chart(fig, use_container_width=True, key="forecast_corr_heatmap")

    with adv_tab2:
        st.caption(
            "Probability that daily attendance exceeds currently allocated seats. "
            "Requires a simulation to have been run first."
        )
        if is_data_loaded():
            scenario = get_active_scenario()
            if scenario and scenario.allocation_results:
                alloc_map = {
                    a.unit_name: a.allocated_seats
                    for a in scenario.allocation_results
                }
                breach_data = []
                for name in unit_names:
                    if name in alloc_map:
                        result = compute_capacity_breach_probability(
                            daily_df, name, alloc_map[name],
                        )
                        if result:
                            breach_data.append(result)

                if breach_data:
                    breach_df = pd.DataFrame(breach_data)
                    breach_df.columns = [
                        "Unit", "Allocated Seats", "Breach Probability",
                        "Est. Breach Days/Month", "Avg Breach Magnitude",
                    ]
                    breach_df["Breach Probability"] = breach_df["Breach Probability"].apply(
                        lambda x: f"{x:.1%}"
                    )
                    st.dataframe(breach_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No breach data available for units in daily attendance data.")
            else:
                st.info("Run a simulation in Scenario Lab first to see breach risk.")
        else:
            st.info("Load base data in Admin tab first.")

    with adv_tab3:
        st.caption(
            "Units grouped by similar temporal attendance patterns (correlation > 0.7). "
            "Same-cluster units have correlated daily attendance and may benefit "
            "from shared floor assignment or coordinated hot-desking."
        )
        clusters = compute_temporal_clustering(daily_df, unit_names)
        if clusters:
            cluster_df = pd.DataFrame(clusters)
            cluster_df.columns = ["Unit", "Cluster ID", "Cluster", "Cluster Size"]
            st.dataframe(cluster_df, use_container_width=True, hide_index=True)
        else:
            st.info("Need at least 2 units with daily data to compute clusters.")
