"""Short-Term View tab — 30/60-day operational attendance view.

Reads:  st.session_state["ci_data_loaded"], ["ci_daily_df"]
Writes: nothing

Renders (top to bottom):
  - City / Building / LOB filters + horizon toggle (30 or 60 days)
  - 4 KPI cards: Peak Predicted, Avg Daily, Buildings >90%, Buildings <60%
  - Holiday callout (if any holiday days fall in the window)
  - Building Risk Details expander  (per-building risk tier table)
  - Floor Utilization expander       (per-floor avg/peak util table)
  - LOB Seat Gap expander            (static Allocated − Headcount per LOB)
  - Insights panel + Daily forecast line chart
  - Day-of-week bar chart + Capacity calendar heatmap

To extend: add new expanders or chart columns after the existing sections.
Engine functions live in engine/capacity_forecast.py — import them inside render().
"""


def render() -> None:
    import streamlit as st
    import pandas as pd
    from engine.capacity_forecast import (
        C_DATE, C_CITY, C_BUILDING, C_FLOOR, C_LOB,
        C_PREDICTED, C_CAPACITY, C_ALLOC, C_SEAT_GAP,
        C_HOL, C_OPT_HOL, C_US_HOL,
        BUILDING_KEY, FLOOR_KEY,
        filter_df,
        get_horizon_df,
        get_weekday_df,
        compute_portfolio_kpis,
        compute_floor_utilization,
        compute_lob_gap_table,
        compute_dow_averages,
        generate_insights_short_term,
        plot_daily_forecast,
        plot_dow_bar,
        plot_capacity_calendar,
        _building_daily,
    )

    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a file.")
        return

    daily_df: pd.DataFrame = st.session_state["ci_daily_df"]
    all_cities = sorted(daily_df[C_CITY].unique().tolist())
    all_lobs   = sorted(daily_df[C_LOB].unique().tolist())
    all_bldgs  = sorted(daily_df[C_BUILDING].unique().tolist())

    # ── Filters ────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sel_cities = st.multiselect("City", all_cities, key="st_city")
    with fc2:
        bldg_opts = sorted(
            daily_df[daily_df[C_CITY].isin(sel_cities)][C_BUILDING].unique().tolist()
        ) if sel_cities else all_bldgs
        sel_bldgs = st.multiselect("Building", bldg_opts, key="st_bldg")
    with fc3:
        sel_lobs = st.multiselect("Line of Business", all_lobs, key="st_lob")

    filtered = filter_df(daily_df, buildings=sel_bldgs or None,
                         cities=sel_cities or None, lobs=sel_lobs or None)

    # ── Horizon toggle ─────────────────────────────────────────────────────
    t1, _ = st.columns([2, 6])
    with t1:
        horizon = st.radio(
            "Horizon", [30, 60],
            format_func=lambda x: f"Next {x} days",
            horizontal=True, key="st_horizon",
        )

    # ── KPI cards ──────────────────────────────────────────────────────────
    kpis      = compute_portfolio_kpis(filtered, horizon_days=horizon)
    total_cap = kpis["total_capacity"]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Peak Predicted",
        f"{kpis['peak_footfall']:,} seats",
        delta=f"{kpis['peak_footfall']/total_cap*100:.0f}% of capacity" if total_cap else None,
        delta_color="off",
    )
    k2.metric(
        "Avg Daily Predicted",
        f"{kpis['avg_footfall']:,} seats",
        delta=f"{kpis['avg_footfall']/total_cap*100:.0f}% avg utilization" if total_cap else None,
        delta_color="off",
    )
    k3.metric(
        "Buildings >90% Peak",
        str(kpis["buildings_above_90"]),
        delta="Over-capacity risk" if kpis["buildings_above_90"] > 0 else "None",
        delta_color="inverse" if kpis["buildings_above_90"] > 0 else "off",
    )
    k4.metric(
        "Buildings <60% Avg",
        str(kpis["buildings_below_60"]),
        delta="Under-utilized" if kpis["buildings_below_60"] > 0 else "None",
        delta_color="off",
    )

    # ── Holiday callout ────────────────────────────────────────────────────
    horizon_df = get_horizon_df(filtered, horizon_days=horizon)
    hol_days = (
        horizon_df[
            (horizon_df[C_HOL] == 1) |
            (horizon_df[C_OPT_HOL] == 1) |
            (horizon_df[C_US_HOL] == 1)
        ][[C_DATE, C_HOL, C_OPT_HOL, C_US_HOL, "Optional Holiday Name"]]
        .drop_duplicates(subset=C_DATE)
        .sort_values(C_DATE)
    ) if "Optional Holiday Name" in horizon_df.columns else pd.DataFrame()

    if not hol_days.empty:
        labels = []
        for _, r in hol_days.iterrows():
            tag = r[C_DATE].strftime("%b %d")
            if r[C_HOL]:
                tag += " (Public Holiday)"
            elif r["Optional Holiday Name"]:
                tag += f" ({r['Optional Holiday Name']})"
            elif r[C_US_HOL]:
                tag += " (US Holiday)"
            labels.append(tag)
        st.info("🗓️ **Holiday days in this window:** " + " · ".join(labels))

    # ── Building Risk Drilldown ────────────────────────────────────────────
    with st.expander("🏢 Building Risk Details", expanded=True):
        wkday_df = get_weekday_df(horizon_df)
        if wkday_df.empty:
            st.info("No weekday data for current selection.")
        else:
            bldg_day  = _building_daily(wkday_df)
            bldg_cap  = (
                wkday_df.drop_duplicates(subset=[C_DATE, *FLOOR_KEY])
                .groupby(BUILDING_KEY)[C_CAPACITY]
                .sum()
                .reset_index()
                .rename(columns={C_CAPACITY: "Total Capacity"})
                .drop_duplicates(subset=C_BUILDING)
            )
            bldg_stats = (
                bldg_day.groupby(BUILDING_KEY)
                .agg(
                    peak_predicted=("predicted_sum", "max"),
                    avg_util=("util", "mean"),
                    peak_util=("util", "max"),
                )
                .reset_index()
                .merge(bldg_cap, on=BUILDING_KEY, how="left")
            )
            bldg_stats["Avg Util %"]  = (bldg_stats["avg_util"]  * 100).round(1)
            bldg_stats["Peak Util %"] = (bldg_stats["peak_util"] * 100).round(1)

            def _risk(row):
                if row["Peak Util %"] > 90: return "🔴 Over Capacity"
                if row["Avg Util %"]  > 75: return "🟡 Watch"
                if row["Avg Util %"]  < 60: return "🔵 Under-utilized"
                return "🟢 Healthy"

            bldg_stats["Risk"] = bldg_stats.apply(_risk, axis=1)
            display = bldg_stats.sort_values("Peak Util %", ascending=False).rename(
                columns={C_CITY: "City", C_BUILDING: "Building",
                         "peak_predicted": "Peak Predicted"}
            )[["Building", "City", "Total Capacity", "Peak Predicted",
               "Avg Util %", "Peak Util %", "Risk"]]

            def _style_risk(df):
                def _c(v):
                    s = str(v)
                    if s.startswith("🔴"): return "color:#dc3545;font-weight:bold"
                    if s.startswith("🟡"): return "color:#856404;font-weight:bold"
                    if s.startswith("🔵"): return "color:#6c757d"
                    return "color:#155724"
                return df.style.map(_c, subset=["Risk"])

            st.dataframe(
                _style_risk(display),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Avg Util %":  st.column_config.NumberColumn(format="%.1f"),
                    "Peak Util %": st.column_config.NumberColumn(format="%.1f"),
                },
            )

    # ── Floor Utilization + LOB Seat Gap ──────────────────────────────────
    col_floor, col_lob = st.columns(2)

    with col_floor:
        with st.expander("🏗️ Floor Utilization", expanded=True):
            floor_util = compute_floor_utilization(filtered, horizon_days=horizon)
            if floor_util.empty:
                st.info("No data.")
            else:
                display_fu = floor_util.rename(columns={C_CITY: "City", C_BUILDING: "Building", C_FLOOR: "Floor"})[
                    ["Building", "City", "Floor", "Avg Util %", "Peak Util %", "Risk"]
                ].sort_values("Peak Util %", ascending=False)

                def _style_floor(df):
                    def _c(v):
                        s = str(v)
                        if s.startswith("🔴"): return "color:#dc3545;font-weight:bold"
                        if s.startswith("🟡"): return "color:#856404;font-weight:bold"
                        if s.startswith("🔵"): return "color:#6c757d"
                        return "color:#155724"
                    return df.style.map(_c, subset=["Risk"])

                st.dataframe(
                    _style_floor(display_fu),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Avg Util %":  st.column_config.NumberColumn(format="%.1f"),
                        "Peak Util %": st.column_config.NumberColumn(format="%.1f"),
                    },
                )

    with col_lob:
        with st.expander("👥 LOB Seat Gap (Allocation vs Headcount)", expanded=True):
            lob_gap = compute_lob_gap_table(filtered)
            if lob_gap.empty:
                st.info("Headcount or allocation data not available.")
            else:
                display_lg = lob_gap.rename(columns={"Total Allocated": "Allocated", "Seat Gap": "Gap"})

                def _style_gap(df):
                    def _c(v):
                        try:
                            return "color:#dc3545;font-weight:bold" if float(v) < 0 else "color:#155724"
                        except (ValueError, TypeError):
                            return ""
                    return df.style.map(_c, subset=["Gap"])

                st.dataframe(_style_gap(display_lg), use_container_width=True, hide_index=True)
                st.caption("Gap = Allocated Seats − Total Headcount. Negative = LOB needs more space than allocated.")

    # ── Insights + Forecast line ───────────────────────────────────────────
    col_ins, col_line = st.columns([2, 3])
    with col_ins:
        st.markdown(
            f'<p class="section-header">Insights — next {horizon} days</p>',
            unsafe_allow_html=True,
        )
        for insight in generate_insights_short_term(filtered, horizon_days=horizon):
            st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

    with col_line:
        st.plotly_chart(
            plot_daily_forecast(filtered, horizon_days=horizon),
            use_container_width=True, key="st_forecast_line",
        )

    # ── DOW bar + Calendar ─────────────────────────────────────────────────
    col_dow, col_cal = st.columns([2, 3])
    with col_dow:
        dow_df = compute_dow_averages(filtered, horizon_days=horizon)
        st.plotly_chart(plot_dow_bar(dow_df), use_container_width=True, key="st_dow_bar")

    with col_cal:
        st.plotly_chart(
            plot_capacity_calendar(filtered, horizon_days=horizon),
            use_container_width=True, key="st_calendar_portfolio",
        )
