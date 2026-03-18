"""Capacity Intelligence — Limited Version
Run with:  streamlit run capacity_intelligence/app.py
"""

import sys
import os

# Make sure local sub-packages are importable regardless of working directory
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data.ci_sample_data import (
    generate_daily_footfall,
    get_buildings_meta,
)
from engine.capacity_forecast import (
    filter_df,
    get_horizon_df,
    compute_portfolio_kpis,
    compute_dow_averages,
    compute_monthly_utilization,
    compute_long_term_kpis,
    compute_city_capacity_metrics,
    generate_insights_short_term,
    generate_insights_long_term,
    apply_scenario_adjustments,
    compute_scenario_kpis,
    compute_building_impact_table,
    compute_live_insights,
    plot_daily_forecast,
    plot_dow_bar,
    plot_capacity_calendar,
    plot_monthly_forecast_simple,
    plot_building_heatmap,
    plot_scenario_wedge,
    SCENARIO_MULTIPLIERS,
    simulate_rto_policy,
    compute_seat_gap_by_building,
    compute_policy_kpis,
    plot_rto_comparison,
    BASELINE_RTO_DAYS,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Capacity Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stMetric label { font-size: 0.78rem !important; }
    .insight-box {
        background: #f8f9fa;
        border-left: 4px solid #1a3c5e;
        padding: 0.9rem 1.1rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        font-size: 0.88rem;
    }
    .section-header {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6c757d;
        margin-bottom: 0.3rem;
        margin-top: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
if "ci_data_loaded" not in st.session_state:
    st.session_state["ci_data_loaded"] = False
if "ci_daily_df" not in st.session_state:
    st.session_state["ci_daily_df"] = None
if "ci_buildings_meta" not in st.session_state:
    st.session_state["ci_buildings_meta"] = None
if "ci_data_source" not in st.session_state:
    st.session_state["ci_data_source"] = None

# ---------------------------------------------------------------------------
# Sidebar — filters only (data loading moved to Admin tab)
# ---------------------------------------------------------------------------
REQUIRED_COLS = {"date", "building_id", "building_name", "city", "country", "lob", "footfall", "capacity"}

with st.sidebar:
    st.divider()
    st.caption("Run: `streamlit run capacity_intelligence/app.py`")

# ---------------------------------------------------------------------------
# App header
# ---------------------------------------------------------------------------
col_h1, col_h2 = st.columns([6, 1])
with col_h1:
    st.markdown("## 📊 Capacity Intelligence")
    st.caption("Transforming predictive footfall data into actionable operational interfaces.")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_short, tab_long, tab_scenario, tab_admin, tab_help = st.tabs([
    "📅 Short-Term View",
    "📈 Long-Term View",
    "🔀 Scenario Planner",
    "⚙️ Admin",
    "📖 Help",
])


# ===========================================================================
# TAB 1 — SHORT-TERM VIEW
# ===========================================================================
with tab_short:
    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a CSV.")
    else:
        daily_df = st.session_state["ci_daily_df"]
        buildings_meta = st.session_state["ci_buildings_meta"]
        bldg_id_to_name = {b["building_id"]: b["building_name"] for b in buildings_meta}
        all_cities = sorted(daily_df["city"].unique().tolist())
        all_lobs = sorted(daily_df["lob"].unique().tolist())

        # --- Filters ---
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            sel_cities_st = st.multiselect("City", all_cities, key="st_city")
        with fc2:
            sel_lobs_st = st.multiselect("Line of Business", all_lobs, key="st_lob")
        with fc3:
            sel_bldgs_st = st.multiselect(
                "Building",
                options=[b["building_id"] for b in buildings_meta],
                format_func=lambda x: bldg_id_to_name.get(x, x),
                key="st_bldg",
            )

        filtered_st = filter_df(
            daily_df,
            buildings=sel_bldgs_st or None,
            cities=sel_cities_st or None,
            lobs=sel_lobs_st or None,
        )

        # --- Toggles ---
        t1, t2 = st.columns([2, 6])
        with t1:
            horizon = st.radio("Horizon", [30, 60], format_func=lambda x: f"Next {x} days",
                               horizontal=True, key="st_horizon")

        st.divider()

        # --- KPIs ---
        kpis = compute_portfolio_kpis(filtered_st, horizon_days=horizon)
        total_cap = kpis["total_capacity"]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Peak Footfall", f"{kpis['peak_footfall']:,}",
                  delta=f"{kpis['peak_footfall']/total_cap*100:.0f}% of capacity" if total_cap else None,
                  delta_color="off")
        k2.metric("Avg Daily Footfall", f"{kpis['avg_footfall']:,}",
                  delta=f"{kpis['avg_footfall']/total_cap*100:.0f}% of capacity" if total_cap else None,
                  delta_color="off")
        k3.metric(
            "Buildings >90% Utilization",
            str(kpis["buildings_above_90"]),
            delta="⚠ Over capacity risk" if kpis["buildings_above_90"] > 0 else "✓ None",
            delta_color="inverse" if kpis["buildings_above_90"] > 0 else "off",
        )
        k4.metric(
            "Buildings <60% Utilization",
            str(kpis["buildings_below_60"]),
            delta="⚠ Under-utilized" if kpis["buildings_below_60"] > 0 else "✓ None",
            delta_color="inverse" if kpis["buildings_below_60"] > 0 else "off",
        )

        # --- Building Risk Drilldown ---
        with st.expander("🏢 Building Risk Details", expanded=True):
            horizon_wdf = get_horizon_df(filtered_st, horizon_days=horizon)
            horizon_wdf = horizon_wdf[horizon_wdf["date"].dt.dayofweek < 5]
            if horizon_wdf.empty:
                st.info("No data for current selection.")
            else:
                _grp = horizon_wdf.groupby(["building_id", "building_name", "city", "lob"])
                bldg_risk = pd.DataFrame({
                    "building_id":    [k[0] for k in _grp.groups],
                    "Building":       [k[1] for k in _grp.groups],
                    "City":           [k[2] for k in _grp.groups],
                    "LoB":            [k[3] for k in _grp.groups],
                    "Capacity":       [int(_grp.get_group(k)["capacity"].iloc[0]) for k in _grp.groups],
                    "Peak Footfall":  [int(_grp.get_group(k)["footfall"].max()) for k in _grp.groups],
                    "Avg Util %":     [round((_grp.get_group(k)["footfall"] / _grp.get_group(k)["capacity"]).mean() * 100, 1) for k in _grp.groups],
                    "Peak Util %":    [round((_grp.get_group(k)["footfall"] / _grp.get_group(k)["capacity"]).max() * 100, 1) for k in _grp.groups],
                }).drop(columns=["building_id"])

                def _risk_label(row):
                    if row["Peak Util %"] > 90:
                        return "🔴 Over Capacity"
                    elif row["Avg Util %"] > 75:
                        return "🟡 Watch"
                    elif row["Avg Util %"] < 60:
                        return "🔵 Under-utilized"
                    return "🟢 Healthy"

                bldg_risk["Risk"] = bldg_risk.apply(_risk_label, axis=1)
                bldg_risk = bldg_risk.sort_values(
                    "Peak Util %", ascending=False
                )[["Building", "City", "LoB", "Capacity", "Peak Footfall", "Avg Util %", "Peak Util %", "Risk"]]

                def _style_risk(df):
                    def _c(val):
                        v = str(val)
                        if v.startswith("🔴"):
                            return "color: #dc3545; font-weight: bold"
                        elif v.startswith("🟡"):
                            return "color: #856404; font-weight: bold"
                        elif v.startswith("🔵"):
                            return "color: #6c757d"
                        return "color: #155724"
                    return df.style.map(_c, subset=["Risk"])

                st.dataframe(_style_risk(bldg_risk), use_container_width=True, hide_index=True)

        st.markdown("")

        # --- Row 2: Insights + Forecast line ---
        col_ins, col_line = st.columns([2, 3])

        with col_ins:
            st.markdown('<p class="section-header">Insights (next {} days)</p>'.format(horizon),
                        unsafe_allow_html=True)
            insights = generate_insights_short_term(filtered_st, horizon_days=horizon)
            for insight in insights:
                st.markdown(
                    f'<div class="insight-box">{insight}</div>',
                    unsafe_allow_html=True,
                )

        with col_line:
            fig_line = plot_daily_forecast(filtered_st, horizon_days=horizon)
            st.plotly_chart(fig_line, use_container_width=True, key="st_forecast_line")

        st.markdown("")

        # --- Row 3: DOW bar + Calendar ---
        col_dow, col_cal = st.columns([2, 3])

        with col_dow:
            dow_df = compute_dow_averages(filtered_st, horizon_days=horizon)
            fig_dow = plot_dow_bar(dow_df)
            st.plotly_chart(fig_dow, use_container_width=True, key="st_dow_bar")

        with col_cal:
            fig_cal = plot_capacity_calendar(filtered_st, horizon_days=horizon)
            st.plotly_chart(fig_cal, use_container_width=True, key="st_calendar_portfolio")


# ===========================================================================
# TAB 2 — LONG-TERM VIEW
# ===========================================================================
with tab_long:
    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a CSV.")
    else:
        daily_df = st.session_state["ci_daily_df"]
        buildings_meta = st.session_state["ci_buildings_meta"]
        bldg_id_to_name = {b["building_id"]: b["building_name"] for b in buildings_meta}
        all_cities = sorted(daily_df["city"].unique().tolist())
        all_lobs = sorted(daily_df["lob"].unique().tolist())
        all_countries = sorted(daily_df["country"].unique().tolist())

        # --- Filters ---
        fl1, fl2, fl3, fl4 = st.columns(4)
        with fl1:
            sel_countries_lt = st.multiselect("Country", all_countries, key="lt_country")
        with fl2:
            sel_cities_lt = st.multiselect("City", all_cities, key="lt_city")
        with fl3:
            sel_lobs_lt = st.multiselect("Line of Business", all_lobs, key="lt_lob")
        with fl4:
            sel_bldgs_lt = st.multiselect(
                "Building",
                options=[b["building_id"] for b in buildings_meta],
                format_func=lambda x: bldg_id_to_name.get(x, x),
                key="lt_bldg",
            )

        filtered_lt = filter_df(
            daily_df,
            buildings=sel_bldgs_lt or None,
            cities=sel_cities_lt or None,
            lobs=sel_lobs_lt or None,
            countries=sel_countries_lt or None,
        )

        # Horizon toggle
        lt_col1, lt_col2 = st.columns([2, 6])
        with lt_col1:
            lt_horizon = st.radio("Horizon", [6, 12],
                                  format_func=lambda x: f"{x} months",
                                  horizontal=True, key="lt_horizon")

        st.divider()

        # --- KPIs ---
        lt_kpis = compute_long_term_kpis(filtered_lt, horizon_months=lt_horizon)
        total_cap_lt = lt_kpis["total_capacity"]

        lk1, lk2, lk3, lk4 = st.columns(4)
        lk1.metric(
            "Avg Monthly Footfall",
            f"{lt_kpis['avg_monthly_footfall']:,}",
            delta=None,
        )
        lk2.metric(
            "Avg Capacity Utilization",
            f"{lt_kpis['avg_util_pct']}%",
            delta="High risk" if lt_kpis["avg_util_pct"] > 85 else None,
            delta_color="inverse" if lt_kpis["avg_util_pct"] > 85 else "off",
        )
        lk3.metric(
            "Surplus Seats",
            f"{lt_kpis['surplus_seats']:+,}",
            delta="Over capacity risk" if lt_kpis["surplus_seats"] < 0 else None,
            delta_color="inverse" if lt_kpis["surplus_seats"] < 0 else "off",
        )
        lk4.metric(
            "Buildings Below 50% Util.",
            str(lt_kpis["buildings_below_50"]),
            delta="Consolidation candidate" if lt_kpis["buildings_below_50"] > 0 else None,
            delta_color="off",
        )

        st.markdown("")

        # --- Row 2: Insights + Monthly forecast ---
        col_ins_lt, col_line_lt = st.columns([2, 3])

        with col_ins_lt:
            st.markdown('<p class="section-header">Long-Range Insights</p>', unsafe_allow_html=True)
            insights_lt = generate_insights_long_term(filtered_lt, horizon_months=lt_horizon)
            for ins in insights_lt:
                st.markdown(f'<div class="insight-box">{ins}</div>', unsafe_allow_html=True)

        with col_line_lt:
            fig_lt_line = plot_monthly_forecast_simple(filtered_lt)
            st.plotly_chart(fig_lt_line, use_container_width=True, key="lt_monthly_line")

        st.markdown("")

        # --- Row 3: Heatmap ---
        st.markdown('<p class="section-header">Monthly Utilization by Building</p>',
                    unsafe_allow_html=True)
        monthly_util_df = compute_monthly_utilization(filtered_lt)
        if not monthly_util_df.empty:
            today_str = pd.Timestamp(date.today()).to_period("M")
            end_period = today_str + lt_horizon
            monthly_util_df = monthly_util_df[
                monthly_util_df["year_month"].apply(lambda p: today_str <= p <= end_period)
            ]
        fig_heatmap = plot_building_heatmap(monthly_util_df)
        st.plotly_chart(fig_heatmap, use_container_width=True, key="lt_heatmap")

        # --- Row 4: Capacity metrics table ---
        st.markdown('<p class="section-header">Capacity Metrics by City</p>', unsafe_allow_html=True)
        metrics_df = compute_city_capacity_metrics(filtered_lt, horizon_months=lt_horizon)

        def style_city_table(df):
            def color_util(val):
                try:
                    v = float(str(val).replace("%", ""))
                    if v > 85:
                        return "color: #dc3545; font-weight: bold"
                    elif v < 55:
                        return "color: #856404"
                except (ValueError, TypeError):
                    pass
                return ""

            def color_surplus(val):
                v = str(val)
                if v.startswith("+") and int(v.replace("+", "")) > 0:
                    return "color: #155724"
                elif v.startswith("-"):
                    return "color: #dc3545; font-weight: bold"
                return ""

            s = df.style
            if "Utilization %" in df.columns:
                s = s.map(color_util, subset=["Utilization %"])
            if "Surplus" in df.columns:
                s = s.map(color_surplus, subset=["Surplus"])
            return s

        if not metrics_df.empty:
            st.dataframe(style_city_table(metrics_df), use_container_width=True, height=200)
        else:
            st.info("No data for current selection.")


# ===========================================================================
# TAB 3 — SCENARIO PLANNER
# ===========================================================================
with tab_scenario:
    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a CSV.")
    else:
        daily_df = st.session_state["ci_daily_df"]
        buildings_meta = st.session_state["ci_buildings_meta"]
        bldg_id_to_name = {b["building_id"]: b["building_name"] for b in buildings_meta}
        all_lobs = sorted(daily_df["lob"].unique().tolist())

        # Mode selector
        sp_mode = st.radio(
            "Scenario mode",
            ["Event Impact", "Policy Simulation"],
            horizontal=True,
            key="sp_mode",
            help=(
                "Event Impact: model a specific disruption or event over a date window. "
                "Policy Simulation: model structural RTO mandate or allocation changes."
            ),
        )
        st.divider()

        # -------------------------------------------------------------------
        # MODE A — EVENT IMPACT
        # -------------------------------------------------------------------
        if sp_mode == "Event Impact":
            col_controls, col_impact = st.columns([3, 7])

            with col_controls:
                st.markdown("### Event Controls")

                sel_lobs_sp = st.multiselect("Filter: Line of Business", all_lobs, key="sp_lob_a")
                sel_bldgs_sp = st.multiselect(
                    "Filter: Building",
                    options=[b["building_id"] for b in buildings_meta],
                    format_func=lambda x: bldg_id_to_name.get(x, x),
                    key="sp_bldg_a",
                )

                st.markdown("")
                st.markdown("**Adjustment Scope**")
                st.caption("Apply adjustments to the whole portfolio or target specific buildings / lines of business.")
                scope_choice = st.radio(
                    "Apply adjustments to",
                    ["📦 Portfolio-wide", "🏢 Specific Buildings", "👥 Specific LoB"],
                    horizontal=False,
                    key="sp_scope_mode",
                )
                if scope_choice == "🏢 Specific Buildings":
                    scope_vals = st.multiselect(
                        "Select buildings",
                        options=[b["building_id"] for b in buildings_meta],
                        format_func=lambda x: bldg_id_to_name.get(x, x),
                        key="sp_scope_bldgs",
                    )
                    adj_scope = "buildings"
                    adj_scope_values = scope_vals or []
                elif scope_choice == "👥 Specific LoB":
                    scope_vals = st.multiselect(
                        "Select Lines of Business",
                        options=all_lobs,
                        key="sp_scope_lob",
                    )
                    adj_scope = "lob"
                    adj_scope_values = scope_vals or []
                else:
                    adj_scope = "all"
                    adj_scope_values = []

                st.markdown("**Event Period**")
                st.caption(
                    "Footfall within this period is adjusted by the selected event. "
                    "Dates outside remain at baseline."
                )
                default_start_a = date.today() + timedelta(days=7)
                default_end_a = date.today() + timedelta(days=21)
                date_range_a = st.date_input(
                    "Event start → end",
                    value=(default_start_a, default_end_a),
                    min_value=date.today(),
                    max_value=date.today() + timedelta(days=365),
                    key="sp_daterange_a",
                )
                if isinstance(date_range_a, (list, tuple)) and len(date_range_a) == 2:
                    dr_start, dr_end = date_range_a[0], date_range_a[1]
                else:
                    dr_start, dr_end = default_start_a, default_end_a

                st.markdown("")
                st.markdown("**Built-in Adjustments**")

                st.markdown('<p class="section-header">Corporate Events</p>', unsafe_allow_html=True)
                adj_townhall = st.checkbox("Townhall  (+20%)", key="sp_townhall")
                adj_leadership = st.checkbox("Leadership Visit  (+15%)", key="sp_leadership")

                st.markdown('<p class="section-header">External Disruptions</p>', unsafe_allow_html=True)
                adj_weather = st.checkbox("Weather Alert  (−30%)", key="sp_weather")
                adj_traffic = st.checkbox("Traffic / Local Disruption  (−20%)", key="sp_traffic")

                st.markdown('<p class="section-header">Calendar Anomalies</p>', unsafe_allow_html=True)
                adj_mandatory = st.checkbox("Mandatory Holiday  (−90%)", key="sp_mandatory")
                adj_optional = st.checkbox("Optional Holiday  (−40%)", key="sp_optional")
                adj_us = st.checkbox("US Holiday  (−25%)", key="sp_us")

                st.markdown("")
                st.markdown("**Custom Factor**")
                custom_pct = st.number_input(
                    "% adjustment (+ = more footfall, − = less)",
                    min_value=-100.0, max_value=200.0, value=0.0, step=5.0,
                    key="sp_custom",
                )

            adjustments = {
                "townhall": adj_townhall,
                "leadership_visit": adj_leadership,
                "weather_alert": adj_weather,
                "traffic_disruption": adj_traffic,
                "mandatory_holiday": adj_mandatory,
                "optional_holiday": adj_optional,
                "us_holiday": adj_us,
            }

            baseline_sp = filter_df(daily_df, buildings=sel_bldgs_sp or None, lobs=sel_lobs_sp or None)
            scenario_sp = apply_scenario_adjustments(
                baseline_sp, date_range=(dr_start, dr_end),
                adjustments=adjustments, custom_factor_pct=custom_pct,
                scope=adj_scope, scope_values=adj_scope_values,
            )

            with col_impact:
                st.markdown("### Event Impact")

                sp_kpis = compute_scenario_kpis(baseline_sp, scenario_sp, (dr_start, dr_end))
                delta_val = sp_kpis["delta"]
                daily_delta = sp_kpis["scenario_avg_daily"] - sp_kpis["baseline_avg_daily"]

                sk1, sk2, sk3 = st.columns(3)
                sk1.metric(
                    "Baseline Avg Daily",
                    f"{sp_kpis['baseline_avg_daily']:,} seats/day",
                )
                sk2.metric(
                    "Scenario Avg Daily",
                    f"{sp_kpis['scenario_avg_daily']:,} seats/day",
                    delta=f"{daily_delta:+,} seats/day" if daily_delta != 0 else None,
                    delta_color="normal" if daily_delta >= 0 else "inverse",
                )
                sk3.metric(
                    "Event Window",
                    f"{sp_kpis['window_days']} days",
                )

                wkdays = sp_kpis.get("window_weekdays", sp_kpis["window_days"])
                if delta_val > 0:
                    st.caption(
                        f"Event window: {sp_kpis['window_days']} calendar days ({wkdays} weekdays) · "
                        f"Total impact: **+{delta_val:,} person-days** above baseline · "
                        f"Avg is weekday-only — comparable to the Short-Term KPI"
                    )
                elif delta_val < 0:
                    st.caption(
                        f"Event window: {sp_kpis['window_days']} calendar days ({wkdays} weekdays) · "
                        f"Total impact: **{delta_val:,} person-days** below baseline · "
                        f"Avg is weekday-only — comparable to the Short-Term KPI"
                    )
                else:
                    st.caption(
                        f"Event window: {sp_kpis['window_days']} calendar days ({wkdays} weekdays) · "
                        f"No adjustment applied — select an event or set a custom factor · "
                        f"Avg is weekday-only — note the Short-Term KPI covers a different date range"
                    )

                sp_horizon = min(90, (dr_end - date.today()).days + 30)
                fig_wedge = plot_scenario_wedge(
                    baseline_sp, scenario_sp, (dr_start, dr_end), horizon_days=sp_horizon
                )
                st.plotly_chart(fig_wedge, use_container_width=True, key="sp_wedge")

                st.markdown('<p class="section-header">Impact by Building</p>', unsafe_allow_html=True)
                impact_df = compute_building_impact_table(baseline_sp, scenario_sp, (dr_start, dr_end))

                def _style_diff(df):
                    def _c(val):
                        try:
                            v = float(val)
                            return "color: #155724; font-weight: bold" if v > 0 else (
                                "color: #dc3545; font-weight: bold" if v < 0 else ""
                            )
                        except (ValueError, TypeError):
                            return ""
                    return df.style.map(_c, subset=["Difference"])

                if not impact_df.empty:
                    st.dataframe(_style_diff(impact_df), use_container_width=True, height=220)
                else:
                    st.info("No buildings match the current filter.")

                # Live Impact Insights
                with st.expander("📊 Live Impact Insights", expanded=True):
                    live_insights = compute_live_insights(
                        baseline_sp, scenario_sp, (dr_start, dr_end),
                        scope=adj_scope, scope_values=adj_scope_values,
                    )
                    for ins in live_insights:
                        st.markdown(f'<div class="insight-box">{ins}</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------
        # MODE B — POLICY SIMULATION
        # -------------------------------------------------------------------
        else:
            col_policy, col_policy_impact = st.columns([3, 7])

            with col_policy:
                st.markdown("### Policy Controls")

                sel_lobs_pb = st.multiselect("Filter: Line of Business", all_lobs, key="sp_lob_b")
                sel_bldgs_pb = st.multiselect(
                    "Filter: Building",
                    options=[b["building_id"] for b in buildings_meta],
                    format_func=lambda x: bldg_id_to_name.get(x, x),
                    key="sp_bldg_b",
                )

                st.markdown("")
                st.markdown("**RTO Mandate**")
                new_rto = st.slider(
                    "Avg office days / week",
                    min_value=1.0, max_value=5.0,
                    value=float(BASELINE_RTO_DAYS),
                    step=0.5, key="sp_rto_days",
                )
                delta_rto = new_rto - BASELINE_RTO_DAYS
                rto_caption = (
                    f"Baseline is {BASELINE_RTO_DAYS} days/week. "
                    + (f"+{delta_rto:.1f} days → footfall increases ~{delta_rto/BASELINE_RTO_DAYS*100:.0f}%"
                       if delta_rto > 0 else
                       f"{delta_rto:.1f} days → footfall decreases ~{abs(delta_rto)/BASELINE_RTO_DAYS*100:.0f}%"
                       if delta_rto < 0 else "No change from baseline.")
                )
                st.caption(rto_caption)

                st.markdown("")
                st.markdown("**Seat Planning Target**")
                target_util_pct = st.slider(
                    "Target utilization % for seat allocation",
                    min_value=50, max_value=95, value=80, step=5,
                    key="sp_target_util",
                )
                st.caption(
                    f"Seats needed = peak footfall ÷ {target_util_pct}%. "
                    "Lower % = more buffer seats planned."
                )

                st.markdown("")
                st.markdown("**Horizon**")
                pb_horizon_opt = st.radio(
                    "View horizon",
                    ["30 days", "60 days", "6 months"],
                    horizontal=True, key="sp_pb_horizon",
                )
                pb_horizon_days = {"30 days": 30, "60 days": 60, "6 months": 180}[pb_horizon_opt]

            baseline_pb = filter_df(daily_df, buildings=sel_bldgs_pb or None, lobs=sel_lobs_pb or None)
            policy_df = simulate_rto_policy(baseline_pb, new_rto_days=new_rto)

            with col_policy_impact:
                st.markdown("### Policy Impact")

                pb_kpis = compute_policy_kpis(
                    baseline_pb, policy_df,
                    target_utilization=target_util_pct / 100.0,
                    horizon_days=pb_horizon_days,
                )

                pk1, pk2, pk3, pk4 = st.columns(4)
                pk1.metric("Current Avg Daily Demand", f"{pb_kpis['base_demand']:,}")
                pk2.metric(
                    "Policy Avg Daily Demand", f"{pb_kpis['policy_demand']:,}",
                    delta=f"{pb_kpis['demand_delta']:+,} seats/day",
                    delta_color="normal" if pb_kpis["demand_delta"] >= 0 else "inverse",
                )
                pk3.metric(
                    "Portfolio Seat Gap",
                    f"{pb_kpis['portfolio_gap']:+,}",
                    delta="Surplus" if pb_kpis["portfolio_gap"] >= 0 else "Deficit",
                    delta_color="off" if pb_kpis["portfolio_gap"] >= 0 else "inverse",
                )
                pk4.metric("Total Capacity", f"{pb_kpis['total_capacity']:,}")

                st.markdown("")

                fig_rto = plot_rto_comparison(baseline_pb, policy_df)
                st.plotly_chart(fig_rto, use_container_width=True, key="sp_rto_chart")

                st.markdown('<p class="section-header">Seat Gap by Building</p>',
                            unsafe_allow_html=True)
                gap_df = compute_seat_gap_by_building(
                    policy_df,
                    target_utilization=target_util_pct / 100.0,
                    horizon_days=pb_horizon_days,
                )

                def _style_gap(df):
                    def _c(val):
                        try:
                            v = float(val)
                            return "color: #155724; font-weight: bold" if v > 0 else (
                                "color: #dc3545; font-weight: bold" if v < 0 else ""
                            )
                        except (ValueError, TypeError):
                            return ""
                    return df.style.map(_c, subset=["Surplus / Deficit"])

                if not gap_df.empty:
                    st.dataframe(_style_gap(gap_df), use_container_width=True, height=280)
                else:
                    st.info("No buildings match the current filter.")


# ===========================================================================
# TAB 4 — ADMIN
# ===========================================================================
with tab_admin:
    st.markdown("### ⚙️ Data Management")
    st.caption("Load sample data or upload your own footfall CSV to activate all views.")

    st.divider()

    # Section A: Data source radio
    admin_source = st.radio(
        "Data source",
        ["Use Sample Data", "Upload your CSV"],
        horizontal=True,
        key="admin_data_source",
    )

    st.markdown("")

    # Persistent status banner — shown whenever data is already loaded
    if st.session_state.get("ci_data_loaded"):
        _df = st.session_state["ci_daily_df"]
        _src = "sample" if st.session_state.get("ci_data_source") == "sample" else "uploaded CSV"
        st.success(
            f"✅ Data active ({_src}) — {_df['building_id'].nunique()} buildings, "
            f"{_df['date'].nunique()} days · All tabs are ready."
        )
        if st.button("Clear data", key="admin_clear", type="secondary"):
            st.session_state["ci_data_loaded"] = False
            st.session_state["ci_daily_df"] = None
            st.session_state["ci_buildings_meta"] = None
            st.session_state["ci_data_source"] = None
            st.rerun()
        st.divider()

    # Section B: Load Sample Data
    if admin_source == "Use Sample Data":
        st.markdown(
            "**Built-in dataset** — 7 synthetic buildings across Bangalore, Hyderabad, Chennai, and Manila, "
            "covering 365 days with realistic day-of-week patterns and growth trends."
        )
        if st.button("Load Sample Data", type="primary", key="admin_load_sample", use_container_width=False):
            with st.spinner("Generating sample data…"):
                st.session_state["ci_daily_df"] = generate_daily_footfall()
                st.session_state["ci_buildings_meta"] = get_buildings_meta()
                st.session_state["ci_data_source"] = "sample"
                st.session_state["ci_data_loaded"] = True
            st.rerun()  # Restart script so all tabs see ci_data_loaded = True immediately

    # Section C: Upload CSV
    else:
        col_tmpl, col_up = st.columns([2, 3])
        with col_tmpl:
            template_df = pd.DataFrame(columns=sorted(REQUIRED_COLS))
            st.download_button(
                "Download CSV template",
                data=template_df.to_csv(index=False),
                file_name="footfall_template.csv",
                mime="text/csv",
                use_container_width=True,
                key="admin_tmpl_dl",
            )
            st.caption(f"Required columns: {', '.join(sorted(REQUIRED_COLS))}")
        with col_up:
            uploaded = st.file_uploader("Upload footfall CSV", type=["csv"], key="admin_upload")
            if uploaded is not None:
                try:
                    user_df = pd.read_csv(uploaded, parse_dates=["date"])
                    missing = REQUIRED_COLS - set(user_df.columns)
                    if missing:
                        st.error(f"Missing columns: {', '.join(sorted(missing))}")
                    elif not st.session_state.get("ci_data_loaded"):
                        # Only load once — avoid re-processing on every rerun while uploader is mounted
                        user_df["date"] = pd.to_datetime(user_df["date"])
                        bldg_cols = ["building_id", "building_name", "city", "country", "lob", "capacity"]
                        meta = (
                            user_df[bldg_cols]
                            .drop_duplicates("building_id")
                            .rename(columns={"capacity": "total_capacity"})
                            .to_dict("records")
                        )
                        st.session_state["ci_daily_df"] = user_df
                        st.session_state["ci_buildings_meta"] = meta
                        st.session_state["ci_data_source"] = "upload"
                        st.session_state["ci_data_loaded"] = True
                        st.rerun()  # Restart so all tabs activate immediately
                except Exception as e:
                    st.error(f"Could not parse file: {e}")

    # Section D: Data Preview
    if st.session_state.get("ci_data_loaded"):
        st.divider()
        st.markdown("### Data Preview")

        prev_df: pd.DataFrame = st.session_state["ci_daily_df"]
        dp1, dp2, dp3 = st.columns(3)
        dp1.metric("Total Records", f"{len(prev_df):,}")
        dp2.metric(
            "Date Range",
            f"{prev_df['date'].min().date()} → {prev_df['date'].max().date()}",
        )
        dp3.metric("Buildings", str(prev_df["building_id"].nunique()))

        st.markdown("")
        st.markdown("**Sample rows (first 20)**")
        st.dataframe(prev_df.head(20), use_container_width=True)

        # Building summary
        st.markdown("")
        st.markdown("**Buildings in dataset**")
        bldg_summary = (
            prev_df.groupby(["building_id", "building_name", "city", "country", "lob"])
            .agg(
                capacity=("capacity", "first"),
                days=("date", "nunique"),
                avg_util=("utilization_pct", "mean"),
            )
            .reset_index()
            .rename(columns={
                "building_id": "ID", "building_name": "Building", "city": "City",
                "country": "Country", "lob": "LoB", "capacity": "Capacity",
                "days": "Days", "avg_util": "Avg Util %",
            })
        )
        bldg_summary["Avg Util %"] = (bldg_summary["Avg Util %"] * 100).round(1).astype(str) + "%"
        st.dataframe(bldg_summary, use_container_width=True)


# ===========================================================================
# TAB 5 — HELP
# ===========================================================================
with tab_help:
    st.markdown("### 📖 How This App Works")
    st.caption("Reference guide for all calculations, formulas, and thresholds used across the app.")

    with st.expander("1 · Data Model", expanded=True):
        st.markdown("""
**Required columns** (for both sample data and uploaded CSV):

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Calendar date of the record |
| `building_id` | string | Unique building identifier (e.g. `BLR-ENG`) |
| `building_name` | string | Human-readable building name |
| `city` | string | City the building is in |
| `country` | string | Country |
| `lob` | string | Line of Business occupying the building |
| `footfall` | integer | Number of people in office on that date |
| `capacity` | integer | Total seat capacity of the building |

`utilization_pct` is derived automatically: `footfall ÷ capacity` (clipped at 130%).

**Sample dataset:** 7 buildings across Bangalore, Hyderabad, Chennai, and Manila · 365 days starting from today · Deterministic (seed = 42 — same data every load).

**Uploaded CSV:** Must include all 8 columns above. Future-dated rows are used as projections. Historical-only files will show actuals, not forecasts, in the horizon views.
""")

    with st.expander("2 · How the Horizon Works", expanded=True):
        st.markdown("""
Both Short-Term and Long-Term views **slice the dataset** to a date window starting from today. No extrapolation is performed.

| Tab | Horizon option | Date range used |
|-----|---------------|-----------------|
| Short-Term | 30 days | `today ≤ date < today + 30` |
| Short-Term | 60 days | `today ≤ date < today + 60` |
| Long-Term | 6 months | `today ≤ date < today + 180` |
| Long-Term | 12 months | `today ≤ date < today + 365` |

**All KPIs and charts use weekdays only (Mon–Fri).** Weekends are excluded from every calculation.

**Why numbers change between horizons:** The sample data has a linear growth trend baked in. Days further in the future have a slightly higher footfall multiplier, so a 60-day window will show higher peak/avg values than a 30-day window for growing buildings. Shrinking buildings (e.g. Manila Ops, −5% growth) show the opposite.
""")

    with st.expander("3 · How Forecasting Works", expanded=True):
        st.markdown("""
**There is no statistical forecasting model** (no ARIMA, Holt-Winters, or Prophet) in this version.

The sample data is generated with a deterministic formula at load time:

```
footfall = base_demand × DOW_multiplier × trend_factor × noise

base_demand    = base_utilization × capacity
                 (e.g. 82% × 500 seats = 410 baseline seats for BLR-ENG)

trend_factor   = 1.0 + annual_growth_rate × (day_number / 365)
                 (linear ramp; e.g. +15%/yr means day 365 = 1.15×)

DOW_multiplier = Mon 0.85 · Tue 1.00 · Wed 1.00 · Thu 0.95 · Fri 0.75
                 Sat 0.05 · Sun 0.02

noise          = 1 + Normal(mean=0, std=0.08)   ← ±8% random variation
                 seed = 42 → same numbers every load
```

**For uploaded data:** The app reads whatever footfall values are in your file. If your file contains future projections, those are displayed as-is. If it is historical only, the horizon views will be empty (no future rows to slice).
""")

    with st.expander("4 · Scenario Planner Calculations", expanded=True):
        st.markdown("""
#### Mode A — Event Impact

The baseline is your filtered dataset, unmodified. An adjustment multiplier is applied to footfall rows that fall **within the event date window** and **within the selected scope**:

```
combined_multiplier = event_mult_1 × event_mult_2 × … × (1 + custom_pct / 100)

scenario_footfall = baseline_footfall × combined_multiplier
    — applied only to: rows where date ∈ [event_start, event_end]
                   AND building/LoB matches the selected scope
```

**Built-in event multipliers:**

| Event | Multiplier | Effect |
|-------|-----------|--------|
| Townhall | ×1.20 | +20% footfall |
| Leadership Visit | ×1.15 | +15% footfall |
| Weather Alert | ×0.70 | −30% footfall |
| Traffic / Local Disruption | ×0.80 | −20% footfall |
| Mandatory Holiday | ×0.10 | −90% footfall |
| Optional Holiday | ×0.60 | −40% footfall |
| US Holiday | ×0.75 | −25% footfall |

Multiple events combine multiplicatively: e.g. Townhall + Optional Holiday = 1.20 × 0.60 = ×0.72 (net −28%).

**KPI cards** show **avg daily footfall (seats/day)** — the same unit as the chart Y-axis. The total person-days impact over the full event window is shown as a sub-caption.

#### Mode B — Policy Simulation

All footfall is scaled linearly relative to the baseline RTO assumption (3.5 days/week):

```
scenario_footfall = baseline_footfall × (new_rto_days / 3.5)
```

Seat gap per building = `capacity − (peak_footfall ÷ target_utilization%)`
- Positive gap = surplus seats available
- Negative gap = seats deficit (capacity expansion needed)
""")

    with st.expander("5 · Risk Thresholds & Utilization", expanded=True):
        st.markdown("""
**Utilization** is always computed as weekday footfall ÷ capacity, then averaged or peaked over the horizon window.

| Risk Label | Condition | Meaning |
|------------|-----------|---------|
| 🔴 Over Capacity | Peak utilization > 90% | At least one day exceeds 90% of capacity in the window |
| 🟡 Watch | Avg utilization > 75% | Average occupancy is high — approaching constraint |
| 🔵 Under-utilized | Avg utilization < 60% | Building is running well below capacity — consolidation candidate |
| 🟢 Healthy | Everything else | Normal operating range |

**"Peak"** = the single highest-footfall weekday within the horizon window.

**"Avg"** = mean daily footfall across all weekdays in the horizon window.

These thresholds are applied in:
- Short-Term KPI cards ("Buildings >90%", "Buildings <60%")
- Building Risk Details drilldown table
- Auto-generated Insights bullets
- Long-Term insights ("projected to exceed 90% avg utilization by…")
""")
