"""Tab 7: Demand Forecasting — trend analysis, probabilistic demand, growth suggestions."""

import streamlit as st
import pandas as pd
import numpy as np

from data.session_store import (
    is_data_loaded, get_units, get_attendance,
    get_daily_attendance_df, set_daily_attendance,
    get_active_scenario, update_scenario,
    add_audit_entry, get_floors, get_rule_config,
)
from data.loader import load_file, parse_daily_attendance
from data.validator import validate_daily_attendance, validate_daily_attendance_cross
from engine.forecasting import (
    compute_unit_trend, compute_overall_trend, compute_dow_patterns,
    compute_percentile_demand, bootstrap_confidence_interval,
    compute_forecast_summary,
    compute_capacity_breach_probability, compute_temporal_clustering,
    compute_week_ahead_forecast, compute_per_unit_forecast,
    compute_peak_day_per_unit, compute_dow_conflict_analysis,
)
from components.charts import (
    attendance_trend_chart, dow_heatmap_chart,
    probabilistic_demand_bar,
    temporal_cluster_dow_chart,
)
from models.scenario import ScenarioOverride
from config.defaults import (
    FORECAST_CONFIDENCE_LEVELS, FORECAST_DEFAULT_MONTHS,
    FORECAST_SHORT_TERM_DAYS_OPTIONS, FORECAST_CAPACITY_ALERT_THRESHOLD,
)


# ── Cached wrappers ────────────────────────────────────────────────────────
# Streamlit rerenders the entire tab on every widget interaction.  These wrappers
# memoize expensive engine calls so they only execute when daily_df actually changes.

@st.cache_data(show_spinner=False)
def _cached_unit_trend(daily_df, unit_name, forecast_months):
    return compute_unit_trend(daily_df, unit_name, forecast_months)

@st.cache_data(show_spinner=False)
def _cached_overall_trend(daily_df, forecast_months):
    return compute_overall_trend(daily_df, forecast_months)

@st.cache_data(show_spinner=False)
def _cached_forecast_summary(daily_df, unit_names_tuple, forecast_months):
    return compute_forecast_summary(daily_df, list(unit_names_tuple), forecast_months)

@st.cache_data(show_spinner=False)
def _cached_percentile_demand(daily_df, unit_name):
    return compute_percentile_demand(daily_df, unit_name)

@st.cache_data(show_spinner=False)
def _cached_bootstrap_ci(daily_df, unit_name, confidence):
    return bootstrap_confidence_interval(daily_df, unit_name, confidence)

@st.cache_data(show_spinner=False)
def _cached_week_ahead_forecast(daily_df, total_capacity, n_days, holiday_dates_tuple):
    return compute_week_ahead_forecast(
        daily_df, total_capacity, n_days,
        list(holiday_dates_tuple) if holiday_dates_tuple else None,
    )

@st.cache_data(show_spinner=False)
def _cached_per_unit_forecast(daily_df, n_days, holiday_dates_tuple):
    return compute_per_unit_forecast(
        daily_df, n_days=n_days,
        holiday_dates=list(holiday_dates_tuple) if holiday_dates_tuple else None,
    )

@st.cache_data(show_spinner=False)
def _cached_dow_patterns(daily_df):
    return compute_dow_patterns(daily_df)

@st.cache_data(show_spinner=False)
def _cached_dow_conflict_analysis(daily_df):
    return compute_dow_conflict_analysis(daily_df)

@st.cache_data(show_spinner=False)
def _cached_peak_day_per_unit(daily_df):
    return compute_peak_day_per_unit(daily_df)

@st.cache_data(show_spinner=False)
def _cached_temporal_clustering(daily_df, unit_names_tuple):
    return compute_temporal_clustering(daily_df, list(unit_names_tuple))


def _render_demand_download(
    daily_df, unit_names, forecast_months,
    summaries, stf_results, alert_days,
    dow_df, conflict, peak_data_tab,
    breach_data, clusters,
):
    """Render the Download Demand Analytics Report section (Excel + PDF)."""
    from datetime import date as _date
    from engine.demand_report_generator import generate_demand_report
    from engine.demand_pdf_report_generator import generate_demand_pdf_report

    st.subheader("Download Demand Analytics Report")
    st.caption(
        "Exports all analytics sections with actionable insights: Forecast Summary, "
        "Short-Term Outlook, DOW Patterns, Capacity Breach Risk, Load Balancing, "
        "Overflow Planning (if simulation run), and Temporal Clusters."
    )

    scenario = get_active_scenario() if is_data_loaded() else None
    floors = get_floors() if is_data_loaded() else []

    _kwargs = dict(
        daily_df=daily_df,
        unit_names=unit_names,
        rule_config=get_rule_config(),
        forecast_months=forecast_months,
        summaries=summaries,
        stf_results=stf_results,
        alert_days=alert_days,
        dow_df=dow_df,
        conflict=conflict,
        peak_data=peak_data_tab,
        breach_data=breach_data,
        clusters=clusters,
        scenario=scenario,
        floors=floors,
    )

    col1, col2 = st.columns(2)
    with col1:
        xlsx_bytes = generate_demand_report(**_kwargs)
        st.download_button(
            label="Download Demand Report (.xlsx)",
            data=xlsx_bytes,
            file_name=f"demand_analytics_{_date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_demand_dl_xlsx",
            use_container_width=True,
        )
    with col2:
        pdf_bytes = generate_demand_pdf_report(**_kwargs)
        st.download_button(
            label="Download Demand Report (.pdf)",
            data=pdf_bytes,
            file_name=f"demand_analytics_{_date.today()}.pdf",
            mime="application/pdf",
            key="btn_demand_dl_pdf",
            use_container_width=True,
        )


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
- **Capacity Breach Risk** — How often actual attendance overflows your allocated seats
- **Temporal Clusters** — Groups units by similar attendance behavior; informs cluster-diverse floor placement

**Integration:** Click *Apply Forecasted Growth* to push data-driven growth % into What-If Analysis.
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
            with st.expander("Preview loaded data", expanded=False):
                preview = daily_df[["date", "unit_name", "in_office_count"]].head(8).copy()
                preview.columns = ["Date", "Unit Name", "In-Office Count"]
                preview["Date"] = preview["Date"].dt.strftime("%Y-%m-%d")
                st.dataframe(preview, use_container_width=True, hide_index=True)
                st.caption("First 8 rows shown. CSV must have exactly these 3 columns.")

    # Guard: need daily data for everything below
    if daily_df is None:
        st.info("Upload daily attendance data above to enable forecasting features.")
        return

    breach_data = []   # populated later if scenario has allocation_results

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

    # Compute trend (overall aggregate or per-unit) — cached per input combination
    if selected_unit == "All Units (Overall)":
        trend = _cached_overall_trend(daily_df, forecast_months)
        chart_label = "All Units (Total)"
    else:
        trend = _cached_unit_trend(daily_df, selected_unit, forecast_months)
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

        tc1, tc2, tc3, tc4, tc5 = st.columns(5)
        tc1.metric("Current Median", f"{trend['current_median']:.0f}")
        tc2.metric("Trend Slope", f"{trend['trend_slope']:+.2f}/day")
        tc3.metric("Residual Std", f"±{trend['residual_std']:.1f}")
        tc4.metric("6M Forecast", f"{trend['six_month_value']:.0f} seats")
        model_label = "Holt-Winters" if trend.get("model_type") == "holt_winters" else "Linear Reg."
        mape = trend.get("mape")
        tc5.metric("Model", model_label,
                   delta=f"MAPE {mape:.1%}" if mape is not None else None,
                   delta_color="off")
    else:
        st.warning(f"Insufficient data for {selected_unit} (need at least 7 days).")

    # Methodology explanation
    with st.expander("How is this forecast projected?", expanded=False):
        if trend and trend.get("model_type") == "holt_winters":
            st.markdown("""
**Methodology: Holt-Winters Additive ETS (Exponential Smoothing)**

1. **Historical data** (light blue dots) — raw daily in-office attendance counts.

2. **EMA line** (solid blue) — 21-day Exponential Moving Average, smoothing daily noise.

3. **Holt-Winters forecast** (dashed orange) — a triple-exponential smoothing model that
   simultaneously tracks three components:
   - **Level** — the current baseline attendance
   - **Trend** — the rate of growth or decline (with damping to prevent runaway projections)
   - **Seasonality** — the Mon–Fri weekly attendance rhythm (e.g., Tuesday/Wednesday peaks)

   The model is fit to business-day-aligned data and projected forward using the learned
   seasonal curve — producing a **realistic wavy forecast** rather than a straight line.

4. **Widening confidence band** (shaded orange) — prediction intervals grow as
   `1.96 × residual_std × √(h/n)`, where *h* = steps ahead and *n* = historical observations.
   The band is deliberately wider at longer horizons to represent genuine uncertainty.

5. **6M Forecast** — end-of-horizon projected value, floored at 0. **MAPE** (Mean Absolute
   Percentage Error) on in-sample fitted values is shown as the model accuracy indicator.
   Use "Apply 6-Month Growth Estimate" in the Forecast Summary to push values to your scenario.

**When HW is used:** Requires ≥ 12 weekday observations and < 20% gaps. Falls back to
Linear Regression for sparse or weekend-heavy data.
            """)
        else:
            st.markdown("""
**Methodology: Linear Regression**

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

5. **6M Forecast** — the projected attendance value at the **end** of the selected horizon
   (e.g., day 180 for a 6-month view), floored at 0. The **Forecast Summary** table shows this
   end-of-period value alongside the absolute and % change from current median. The 6M Change %
   is bounded to ±100% to avoid artefacts from noisy short time-series. Use "Apply 6-Month Growth
   Estimate" in the summary below to push these values to your active scenario.

**Limitations:** Linear trend assumes constant growth rate. Seasonal patterns (e.g., holiday dips)
or structural changes (e.g., new RTO policy) may cause the actual trajectory to deviate.
Holt-Winters ETS activates automatically once ≥ 12 weekday observations are available.
            """)

    # ── Section 3: Forecast Summary ────────────────────────────────────────
    st.divider()
    st.subheader("Forecast Summary (All Units)")

    summaries = _cached_forecast_summary(daily_df, tuple(unit_names), forecast_months)
    if summaries:
        summary_df = pd.DataFrame(summaries)
        display_df = summary_df[[
            "unit_name", "current_median", "current_peak",
            "forecasted_median", "six_month_change", "six_month_change_pct", "trend_direction",
        ]].copy()
        display_df["six_month_change"] = display_df["six_month_change"].apply(
            lambda x: f"+{x}" if x > 0 else str(x)
        )
        display_df["six_month_change_pct"] = display_df["six_month_change_pct"].apply(
            lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%"
        )
        display_df.columns = [
            "Unit", "Current Median", "Current Peak",
            f"Forecast Median ({forecast_months}m)",
            "6M Change (seats)", "6M Change %", "Trend",
        ]
        st.caption(
            f"Forecast Median = projected attendance at end of {forecast_months}-month horizon. "
            "Negative forecasts floored at 0. 6M Change % bounded to ±100% to suppress noise artefacts."
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Apply button
        if is_data_loaded():
            if st.button(
                "Apply 6-Month Growth Estimate to Active Scenario",
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
                        f"Applied 6-month growth estimates to {len(summaries)} units "
                        f"in scenario '{scenario.name}'. "
                        f"Re-run Policy Simulation in What-If Analysis to see updated demand."
                    )
                elif scenario and scenario.is_locked:
                    st.warning("Active scenario is locked. Unlock it first.")
                else:
                    st.warning("No active scenario found.")

    # ── Section 4: Probabilistic Demand ────────────────────────────────────
    st.divider()
    st.subheader("Probabilistic Seat Demand")
    st.caption(
        "How many seats does your **attendance history** suggest at a given confidence level? "
        "This is a *descriptive* view — no growth, RTO policy, or floor constraints applied. "
        "Compare against your **scenario allocation** (prescriptive: includes policy, RTO factor, "
        "growth assumptions, and floor constraints) to spot over- or under-allocation."
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
        result = _cached_percentile_demand(daily_df, name)
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

        # Fetch current allocation from active scenario (if available)
        alloc_map = {}
        if is_data_loaded():
            _scen = get_active_scenario()
            if _scen and _scen.allocation_results:
                alloc_map = {a.unit_name: a.allocated_seats for a in _scen.allocation_results}

        # Detail table with bootstrap CI + scenario allocation comparison
        detail_rows = []
        for d in demand_data:
            bs = _cached_bootstrap_ci(daily_df, d["unit_name"], confidence)
            current_alloc = alloc_map.get(d["unit_name"])
            pct_val = d["percentiles"][confidence]
            detail_rows.append({
                "Unit": d["unit_name"],
                "Median": d["median"],
                "Peak": d["peak"],
                f"{confidence:.0%} Percentile": pct_val,
                "Current Allocation": current_alloc if current_alloc is not None else "—",
                "vs Allocation": (
                    f"{current_alloc - pct_val:+,}" if current_alloc is not None else "—"
                ),
                "Savings vs Peak": d["savings_vs_peak"][confidence],
                "Bootstrap CI": f"[{bs['ci_lower']}, {bs['ci_upper']}]" if bs else "N/A",
                "Observations": d["n_observations"],
            })
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
        if alloc_map:
            st.caption(
                "**vs Allocation**: positive = scenario assigns more seats than percentile demand "
                "(possible right-sizing opportunity) · "
                "negative = scenario assigns fewer seats (potential overflow risk)"
            )

    # ── Section 4b: Short-Term Demand Forecast ─────────────────────────────
    st.divider()
    st.subheader("Short-Term Seat Demand Forecast")
    st.caption(
        "**How many seats will we need over the next 1–4 weeks?** "
        "Built from your historical day-of-week patterns with a trend-slope recency correction. "
        "Red bars = >90% capacity risk · Orange = >65% · Green = comfortable. "
        "Holidays configured in Admin are automatically excluded."
    )

    # Horizon selector + per-unit toggle
    stf_col1, stf_col2 = st.columns([3, 1])
    with stf_col1:
        stf_horizon = st.radio(
            "Forecast Horizon",
            options=FORECAST_SHORT_TERM_DAYS_OPTIONS,
            format_func=lambda x: f"{x} days (~{x // 5} wk{'s' if x // 5 != 1 else ''})",
            horizontal=True,
            index=0,
            key="stf_horizon_radio",
        )
        st.caption("5 days = this week · 10 days = next 2 weeks · 15 days = 3 weeks · 21 days = one month")
    with stf_col2:
        stf_per_unit = st.toggle("Per-unit breakdown", value=False, key="stf_per_unit_toggle")

    # Get holiday dates and total capacity
    rule_config_stf = get_rule_config()
    holiday_dates_stf = rule_config_stf.get("holiday_dates", [])
    total_cap_stf = 0
    if is_data_loaded():
        floors_stf = get_floors()
        if floors_stf:
            total_cap_stf = sum(f.total_seats for f in floors_stf)

    stf_results = _cached_week_ahead_forecast(
        daily_df, total_cap_stf, stf_horizon,
        tuple(holiday_dates_stf) if holiday_dates_stf else (),
    )

    if stf_results:
        import plotly.graph_objects as go

        alert_days = [r for r in stf_results if r["capacity_pct"] > FORECAST_CAPACITY_ALERT_THRESHOLD]
        peak_seats = max(r["expected_seats"] for r in stf_results)

        stf_m1, stf_m2, stf_m3 = st.columns(3)
        stf_m1.metric("Forecast Days", stf_horizon)
        stf_m2.metric("Capacity Risk Days (>90%)", len(alert_days))
        stf_m3.metric("Peak Forecast", f"{peak_seats:,} seats")

        if alert_days:
            worst = max(alert_days, key=lambda r: r["capacity_pct"])
            st.error(
                f"**{len(alert_days)} day{'s' if len(alert_days) != 1 else ''} above 90% capacity** · "
                f"Highest: **{worst['weekday_name']}** at {worst['capacity_pct']:.0%} utilization"
            )

        bar_colors = [
            "#EF4444" if r["capacity_pct"] > FORECAST_CAPACITY_ALERT_THRESHOLD
            else ("#F59E0B" if r["capacity_pct"] > 0.65 else "#10B981")
            for r in stf_results
        ]
        text_labels = [
            f"{r['capacity_pct']:.0%}" if total_cap_stf > 0 else f"{r['expected_seats']:,}"
            for r in stf_results
        ]

        fig_stf = go.Figure(go.Bar(
            x=[r["short_label"] for r in stf_results],
            y=[r["expected_seats"] for r in stf_results],
            marker_color=bar_colors,
            text=text_labels,
            textposition="outside",
        ))
        if total_cap_stf > 0:
            fig_stf.add_hline(
                y=total_cap_stf * FORECAST_CAPACITY_ALERT_THRESHOLD,
                line_dash="dot", line_color="#EF4444",
                annotation_text="90% capacity threshold",
            )
        fig_stf.update_layout(
            title=f"Company-Wide Seat Demand — Next {stf_horizon} Business Days",
            yaxis_title="Expected Seats",
            showlegend=False,
            height=360,
            margin=dict(t=50, b=20),
        )
        st.plotly_chart(fig_stf, use_container_width=True, key="stf_company_bar")

        if holiday_dates_stf:
            st.caption(f"Holidays excluded: {', '.join(str(h) for h in holiday_dates_stf)}")

        # ── Overflow Floor Planning Advisory ───────────────────────────────
        if alert_days and is_data_loaded():
            with st.expander("Peak Day Overflow Planning", expanded=True):
                st.caption(
                    "On capacity-breach days, these floors have unallocated seats that can temporarily absorb overflow. "
                    "Coordinate with Facilities to designate them as flex space on those specific days — no permanent reassignment needed."
                )
                _of_scenario = get_active_scenario()
                if _of_scenario and _of_scenario.floor_assignments and _of_scenario.allocation_results:
                    from engine.spatial import get_floor_utilization
                    _of_floors = get_floors()
                    _of_util = get_floor_utilization(_of_floors, _of_scenario.floor_assignments)

                    # Floors with spare capacity (potential overflow destinations)
                    _flex_floors = sorted(
                        [f for f in _of_util if f["available_seats"] > 0],
                        key=lambda f: f["available_seats"], reverse=True,
                    )
                    # Units where current demand exceeds allocated seats
                    _at_risk = sorted(
                        [a for a in _of_scenario.allocation_results if a.seat_gap < 0],
                        key=lambda a: a.seat_gap,
                    )

                    of_c1, of_c2 = st.columns(2)

                    with of_c1:
                        st.markdown("**Capacity risk days**")
                        st.dataframe(
                            pd.DataFrame([{
                                "Day": r["weekday_name"],
                                "Expected Seats": r["expected_seats"],
                                "Capacity %": f"{r['capacity_pct']:.0%}",
                            } for r in alert_days]),
                            use_container_width=True, hide_index=True,
                        )

                    with of_c2:
                        if _flex_floors:
                            st.markdown("**Available overflow floors**")
                            st.dataframe(
                                pd.DataFrame([{
                                    "Floor": f["floor_id"],
                                    "Tower": f["tower_id"],
                                    "Spare Seats": f["available_seats"],
                                    "Current Use": f"{f['utilization_pct']:.0%}",
                                } for f in _flex_floors[:6]]),
                                use_container_width=True, hide_index=True,
                            )
                        else:
                            st.warning("No floors have spare seats. Consider adding capacity in What-If Analysis.")

                    if _at_risk:
                        st.markdown("**Units with seat shortfall** (demand > allocation — most in need of overflow space)")
                        st.dataframe(
                            pd.DataFrame([{
                                "Unit": a.unit_name,
                                "Allocated Seats": a.allocated_seats,
                                "Demand": a.effective_demand_seats,
                                "Gap": a.seat_gap,
                            } for a in _at_risk]),
                            use_container_width=True, hide_index=True,
                        )

                    st.info(
                        "**Overflow Tip:** Direct the units in the shortfall table above to the highest spare-seat floors on peak days. "
                        "No changes to the scenario are needed — this is a temporary operational arrangement."
                    )
                else:
                    st.info("Run a **Policy Simulation** in What-If Analysis first to see floor-level overflow options.")

        # Per-unit breakdown
        if stf_per_unit:
            unit_fcast = _cached_per_unit_forecast(
                daily_df, stf_horizon,
                tuple(holiday_dates_stf) if holiday_dates_stf else (),
            )
            if unit_fcast:
                df_uf = pd.DataFrame(unit_fcast)
                pivot_uf = df_uf.pivot_table(
                    index="unit_name", columns="short_label",
                    values="expected_seats", aggfunc="first",
                )
                pivot_uf.index.name = "Unit"
                pivot_uf.columns.name = None
                st.dataframe(pivot_uf, use_container_width=True)
                st.caption("Expected in-office headcount per unit per business day.")
    else:
        st.info("Need at least 7 days of attendance data to generate a short-term forecast.")

    # ── Section 5: Day-of-Week Patterns ────────────────────────────────────
    st.divider()
    st.subheader("Day-of-Week Attendance Patterns")

    dow_df = _cached_dow_patterns(daily_df)
    if not dow_df.empty:
        fig = dow_heatmap_chart(dow_df)
        st.plotly_chart(fig, use_container_width=True, key="dow_heatmap_chart")
        st.caption(
            "Median in-office count by day of week. Use this to identify peak days "
            "(e.g., Tue/Wed) and low-attendance days suitable for hot-desking policies. "
            "See **Peak Day Load Balancing Advisory** below to find which units drive crowding and get stagger suggestions."
        )

    # ── Section 5b: Peak Day Load Balancing Advisory ───────────────────────
    # Pre-compute so we can auto-expand when overloaded days are detected
    conflict = _cached_dow_conflict_analysis(daily_df)
    _has_overload = bool(conflict.get("overloaded_days"))

    with st.expander("Peak Day Load Balancing Advisory", expanded=_has_overload):
        st.markdown(
            "Identifies departments whose peak days cluster on the same weekday, "
            "creating avoidable load spikes. Shift suggestions help managers negotiate "
            "voluntary RTO day changes to flatten the weekly demand curve. "
            "**Red bars** below indicate days where total attendance exceeds 115% of the weekly average."
        )

        if conflict["day_loads"]:
            import plotly.graph_objects as go

            day_order_dow = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            loads = [conflict["day_loads"].get(d, 0) for d in day_order_dow]
            overloaded = conflict["overloaded_days"]
            bar_colors_dow = [
                "#EF4444" if d in overloaded else "#4A90D9"
                for d in day_order_dow
            ]

            fig_dow_load = go.Figure(go.Bar(
                x=day_order_dow,
                y=loads,
                marker_color=bar_colors_dow,
                text=[f"{v:,}" for v in loads],
                textposition="outside",
            ))
            fig_dow_load.update_layout(
                title="Company-Wide Daily Load (Sum of All Unit Medians)",
                yaxis_title="Total Expected Seats",
                showlegend=False,
                height=300,
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig_dow_load, use_container_width=True, key="dow_load_bar")

            if overloaded:
                st.warning(
                    f"**Overloaded days: {', '.join(overloaded)}** — "
                    f"these days carry more than {int((1.15 - 1) * 100)}% above average load."
                )
            else:
                st.success("Load is well-balanced across the week — no overloaded days detected.")

            # Peak Day per Unit table
            peak_data_tab = _cached_peak_day_per_unit(daily_df)
            if peak_data_tab:
                st.markdown("**Peak Day per Unit**")
                peak_rows = [{
                    "Unit": p["unit_name"],
                    "Peak Day": p["peak_day_name"],
                    "Peak Median": p["peak_day_median"],
                    "Avg Median": p["overall_median"],
                    "Peak Ratio": f"{p['peak_ratio']:.2f}×",
                    "Overloaded Day?": "⚠️ Yes" if p["peak_day_name"] in overloaded else "✅ No",
                } for p in peak_data_tab]
                st.dataframe(pd.DataFrame(peak_rows), use_container_width=True, hide_index=True)

            # Stagger suggestions
            suggestions = conflict["suggestions"]
            if suggestions:
                st.markdown("**Stagger Suggestions**")
                sug_rows = [{
                    "Unit": s["unit_name"],
                    "Current Peak Day": s["current_peak_day"],
                    "Suggested Shift To": s["suggested_day"],
                    "Est. Load Moved Off Peak Day": s["load_reduction"],
                } for s in suggestions]
                st.dataframe(pd.DataFrame(sug_rows), use_container_width=True, hide_index=True)
                st.info(
                    "These suggestions are **advisory only** — share with unit managers to "
                    "negotiate voluntary RTO day shifts. No changes are applied automatically."
                )
            elif overloaded:
                st.info("No specific shift suggestions could be generated for overloaded days.")
        else:
            st.info("Need daily attendance data across multiple units to run conflict analysis.")

    # ── Section 6: Advanced Insights ──────────────────────────────────────
    st.divider()
    st.subheader("Advanced Insights")

    adv_tab1, adv_tab2 = st.tabs([
        "⚠️ Capacity Breach Risk", "🔗 Temporal Clusters",
    ])

    with adv_tab1:
        st.caption(
            "How often does actual attendance exceed your allocated seats? "
            "Based on your historical daily data — no guesswork, just your own numbers. "
            "Requires a Policy Simulation to have been run first."
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
                    import math

                    def _risk_tier(prob):
                        if prob >= 0.20:
                            return "🔴 High"
                        if prob >= 0.10:
                            return "🟡 Medium"
                        return "🟢 Low"

                    def _seats_to_fix(magnitude):
                        return int(math.ceil(magnitude / 5) * 5) if magnitude > 0 else 0

                    # Summary callouts
                    high_risk = [d for d in breach_data if d["breach_probability"] >= 0.20]
                    most_critical = max(breach_data, key=lambda d: d["expected_breach_days_per_month"])
                    if high_risk:
                        st.warning(
                            f"**{len(high_risk)} unit{'s' if len(high_risk) != 1 else ''} at high overflow risk** · "
                            f"Most critical: **{most_critical['unit_name']}** — "
                            f"~{most_critical['expected_breach_days_per_month']:.0f} overflow days/month"
                        )
                    else:
                        st.success(
                            f"No units at high overflow risk · Most at-risk: **{most_critical['unit_name']}** — "
                            f"~{most_critical['expected_breach_days_per_month']:.0f} overflow days/month"
                        )

                    # Redesigned table
                    rows = []
                    for d in breach_data:
                        prob = d["breach_probability"]
                        mag = d["avg_breach_magnitude"]
                        rows.append({
                            "Risk": _risk_tier(prob),
                            "Unit": d["unit_name"],
                            "Seats Allocated": d["allocated_seats"],
                            "% Days Overflow": f"{prob:.0%} of days",
                            "Overflow Days/Month": f"~{d['expected_breach_days_per_month']:.0f} days",
                            "Extra People Needed": f"+{mag:.0f} people" if mag > 0 else "none",
                            "Seats to Add (Fix)": f"+{_seats_to_fix(mag)}" if mag > 0 else "—",
                        })
                    # Sort by risk: high first
                    risk_order = {"🔴 High": 0, "🟡 Medium": 1, "🟢 Low": 2}
                    rows.sort(key=lambda r: risk_order.get(r["Risk"], 9))
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.caption(
                        "**Risk:** 🔴 High = overflows 1 in 5 days or more · "
                        "🟡 Medium = 1 in 10 days · 🟢 Low = rare  |  "
                        "**Seats to Add** = average overflow gap rounded to nearest 5 — "
                        "adding this many seats would eliminate most overflow days."
                    )
                else:
                    st.info("No breach data available for units in daily attendance data.")
            else:
                st.info("Run a Policy Simulation in the What-If Analysis tab first to see breach risk.")
        else:
            st.info("Load base data in Admin tab first.")

    with adv_tab2:
        st.markdown(
            "Units are grouped by how similarly their in-office attendance moves week-over-week. "
            "Two units in the same group have a correlation ≥ 0.7 — meaning when one peaks, the other "
            "does too. Units in different groups have largely independent or opposite patterns."
        )
        clusters = _cached_temporal_clustering(daily_df, tuple(unit_names))
        if clusters:
            _PALETTE = ["#4A90D9", "#E8734A", "#2ECC71", "#9B59B6", "#F39C12", "#1ABC9C"]

            # Persist cluster map for use by the planning engine
            cluster_map = {r["unit_name"]: r["cluster_id"] for r in clusters}
            st.session_state["unit_cluster_map"] = cluster_map

            # Build group → members map
            cluster_groups: dict = {}
            for row in clusters:
                cluster_groups.setdefault(row["cluster_label"], []).append(row["unit_name"])

            # ── Cluster Cards ─────────────────────────────────────────
            st.markdown("**Unit Groupings**")
            card_cols = st.columns(max(1, len(cluster_groups)))
            for col, group_label in zip(card_cols, sorted(cluster_groups.keys())):
                members = cluster_groups[group_label]
                idx = int(group_label.split()[-1]) - 1
                color = _PALETTE[idx % len(_PALETTE)]
                with col:
                    st.markdown(
                        f"<div style='border-left:4px solid {color};padding:8px 12px;"
                        f"background:#f8f9fa;border-radius:4px;margin-bottom:4px'>"
                        f"<b style='color:{color}'>{group_label}</b>&nbsp;"
                        f"<small>({len(members)} unit{'s' if len(members) != 1 else ''})</small>"
                        f"<br><br>"
                        + "".join(f"<div>• {m}</div>" for m in members)
                        + "</div>",
                        unsafe_allow_html=True,
                    )

            # ── Planning implication callout ───────────────────────────
            st.info(
                "**Planning implication:** Units in the same group should ideally NOT be placed on the same floor. "
                "They peak simultaneously, so a floor shared only by same-group units will be over-capacity on peak days. "
                "Cross-group co-location (e.g., Group 1 + Group 2 on the same floor) means their peaks offset each other "
                "— steadier floor utilization and lower saturation risk. "
                "Enable **Cluster-Diverse Floor Placement** in What-If Analysis to apply this automatically."
            )

            # ── DOW Profile Chart ──────────────────────────────────────
            st.markdown("**Why are they grouped? — Attendance Profile by Day**")
            if not dow_df.empty:
                fig_clust = temporal_cluster_dow_chart(clusters, dow_df)
                st.plotly_chart(fig_clust, use_container_width=True, key="temporal_cluster_dow")

            st.caption(
                "Groups with different peak days (e.g., Group 1 peaks Tue, Group 2 peaks Thu) "
                "can safely share desks — their demand doesn't overlap."
            )

            # ── Cluster Placement Advisory ─────────────────────────────
            if is_data_loaded():
                adv_scenario = get_active_scenario()
                if adv_scenario and adv_scenario.floor_assignments:
                    with st.expander("Cluster Placement Advisory — Current Floor Assignments", expanded=False):
                        from collections import defaultdict

                        def _build_advisory_rows(floor_assignments, cmap):
                            fu: dict = defaultdict(list)
                            for fa in floor_assignments:
                                fu[f"{fa.tower_id} F{fa.floor_number}"].append(fa.unit_name)
                            rows = []
                            for label, members in sorted(fu.items()):
                                cids = {cmap.get(u) for u in members if cmap.get(u) is not None}
                                n = len(cids)
                                risk = "⚠️ Concentrated" if n <= 1 else "✅ Diversified"
                                rows.append({
                                    "Floor": label,
                                    "Units": ", ".join(members),
                                    "Distinct Groups": n,
                                    "Peak Risk": risk,
                                })
                            return rows

                        advisory_rows = _build_advisory_rows(adv_scenario.floor_assignments, cluster_map)
                        n_concentrated = sum(1 for r in advisory_rows if r["Peak Risk"].startswith("⚠️"))
                        n_total = len(advisory_rows)

                        # Summary + action button
                        if n_concentrated > 0:
                            st.warning(
                                f"**{n_concentrated} of {n_total} floors** have all units from the same "
                                f"attendance group — they will all peak on the same days."
                            )
                        else:
                            st.success(f"All {n_total} floors are diversified across attendance groups.")

                        if n_concentrated > 0 and adv_scenario.allocation_results:
                            if st.button(
                                "Apply Cluster-Diverse Placement (Re-assign Floors)",
                                type="primary",
                                key="btn_apply_cluster_placement",
                                help=(
                                    "Re-assigns floor seats using your current seat demand — "
                                    "no changes to allocation amounts. "
                                    "Prefers placing different attendance groups on the same floor."
                                ),
                            ):
                                from engine.spatial import assign_units_to_floors as _assign_floors
                                _excluded = list(adv_scenario.params.excluded_floors or [])
                                _floors = get_floors()
                                _new_assignments, _ = _assign_floors(
                                    adv_scenario.allocation_results,
                                    _floors,
                                    _excluded,
                                    cluster_map=cluster_map,
                                    diversity_weight=800,
                                )
                                adv_scenario.floor_assignments = _new_assignments
                                update_scenario(adv_scenario)
                                add_audit_entry(
                                    "cluster_placement", adv_scenario.scenario_id,
                                    "floor_assignments", "original", "cluster_diverse",
                                    rationale="Applied cluster-diverse floor placement from Demand Analytics",
                                )
                                st.success("Floor assignments updated. Refreshing advisory...")
                                st.rerun()

                        # Advisory table
                        st.dataframe(
                            pd.DataFrame(advisory_rows),
                            use_container_width=True, hide_index=True,
                        )
                        st.caption(
                            "⚠️ Concentrated = all units on this floor share the same attendance group "
                            "— they'll all peak on the same days, raising saturation risk. "
                            "✅ Diversified = multiple groups present, peaks are spread."
                        )
        else:
            st.info("Need at least 2 units with daily data to compute clusters.")

    # ── Download Report ────────────────────────────────────────────────────
    st.divider()
    _render_demand_download(
        daily_df, unit_names, forecast_months,
        summaries, stf_results, alert_days,
        dow_df, conflict, peak_data_tab,
        breach_data, clusters,
    )
