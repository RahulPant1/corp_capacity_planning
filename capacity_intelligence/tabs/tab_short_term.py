"""Short-Term View tab — 30/60-day operational footfall view."""


def render() -> None:
    import streamlit as st
    import pandas as pd
    from engine.capacity_forecast import (
        filter_df,
        get_horizon_df,
        compute_portfolio_kpis,
        compute_dow_averages,
        generate_insights_short_term,
        plot_daily_forecast,
        plot_dow_bar,
        plot_capacity_calendar,
    )

    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a CSV.")
        return

    daily_df: pd.DataFrame = st.session_state["ci_daily_df"]
    buildings_meta: list = st.session_state["ci_buildings_meta"]
    bldg_id_to_name = {b["building_id"]: b["building_name"] for b in buildings_meta}
    all_cities = sorted(daily_df["city"].unique().tolist())
    all_lobs = sorted(daily_df["lob"].unique().tolist())

    # --- Filters: City | Building | LoB ---
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sel_cities = st.multiselect("City", all_cities, key="st_city")
    with fc2:
        # Cascade: buildings filtered to selected cities
        if sel_cities:
            bldg_opts = sorted(
                daily_df[daily_df["city"].isin(sel_cities)]["building_id"].unique().tolist()
            )
        else:
            bldg_opts = [b["building_id"] for b in buildings_meta]
        sel_bldgs = st.multiselect(
            "Building",
            options=bldg_opts,
            format_func=lambda x: bldg_id_to_name.get(x, x),
            key="st_bldg",
        )
    with fc3:
        sel_lobs = st.multiselect("Line of Business", all_lobs, key="st_lob")

    filtered = filter_df(
        daily_df,
        buildings=sel_bldgs or None,
        cities=sel_cities or None,
        lobs=sel_lobs or None,
    )

    # --- Horizon toggle ---
    t1, _ = st.columns([2, 6])
    with t1:
        horizon = st.radio(
            "Horizon", [30, 60],
            format_func=lambda x: f"Next {x} days",
            horizontal=True, key="st_horizon",
        )

    st.divider()

    # --- KPI cards ---
    kpis = compute_portfolio_kpis(filtered, horizon_days=horizon)
    total_cap = kpis["total_capacity"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Peak Footfall", f"{kpis['peak_footfall']:,}",
        delta=f"{kpis['peak_footfall']/total_cap*100:.0f}% of capacity" if total_cap else None,
        delta_color="off",
    )
    k2.metric(
        "Avg Daily Footfall", f"{kpis['avg_footfall']:,}",
        delta=f"{kpis['avg_footfall']/total_cap*100:.0f}% of capacity" if total_cap else None,
        delta_color="off",
    )
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
        horizon_df = get_horizon_df(filtered, horizon_days=horizon)
        weekday_df = horizon_df[horizon_df["date"].dt.dayofweek < 5]
        if weekday_df.empty:
            st.info("No data for current selection.")
        else:
            # Aggregate to building-day level so tower rows are summed correctly
            bldg_day = (
                weekday_df.groupby(["date", "building_id", "building_name", "city", "lob"])
                .agg(footfall=("footfall", "sum"), capacity=("capacity", "sum"))
                .reset_index()
            )
            bldg_day["util"] = bldg_day["footfall"] / bldg_day["capacity"]
            bldg_stats = (
                bldg_day.groupby(["building_id", "building_name", "city", "lob"])
                .agg(
                    Capacity=("capacity", "first"),
                    peak_footfall=("footfall", "max"),
                    avg_util=("util", "mean"),
                    peak_util=("util", "max"),
                )
                .reset_index()
                .rename(columns={
                    "building_name": "Building", "city": "City", "lob": "LoB",
                    "peak_footfall": "Peak Footfall",
                })
            )
            bldg_stats["Avg Util %"] = (bldg_stats["avg_util"] * 100).round(1)
            bldg_stats["Peak Util %"] = (bldg_stats["peak_util"] * 100).round(1)

            def _risk_label(row):
                if row["Peak Util %"] > 90:
                    return "🔴 Over Capacity"
                elif row["Avg Util %"] > 75:
                    return "🟡 Watch"
                elif row["Avg Util %"] < 60:
                    return "🔵 Under-utilized"
                return "🟢 Healthy"

            bldg_stats["Risk"] = bldg_stats.apply(_risk_label, axis=1)
            display = bldg_stats.sort_values("Peak Util %", ascending=False)[
                ["Building", "City", "LoB", "Capacity", "Peak Footfall", "Avg Util %", "Peak Util %", "Risk"]
            ]

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

            st.dataframe(_style_risk(display), use_container_width=True, hide_index=True)

    st.markdown("")

    # --- Row 2: Insights + Forecast line ---
    col_ins, col_line = st.columns([2, 3])
    with col_ins:
        st.markdown(
            f'<p class="section-header">Insights (next {horizon} days)</p>',
            unsafe_allow_html=True,
        )
        for insight in generate_insights_short_term(filtered, horizon_days=horizon):
            st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

    with col_line:
        st.plotly_chart(
            plot_daily_forecast(filtered, horizon_days=horizon),
            use_container_width=True, key="st_forecast_line",
        )

    st.markdown("")

    # --- Row 3: DOW bar + Calendar ---
    col_dow, col_cal = st.columns([2, 3])
    with col_dow:
        dow_df = compute_dow_averages(filtered, horizon_days=horizon)
        st.plotly_chart(plot_dow_bar(dow_df), use_container_width=True, key="st_dow_bar")

    with col_cal:
        st.plotly_chart(
            plot_capacity_calendar(filtered, horizon_days=horizon),
            use_container_width=True, key="st_calendar_portfolio",
        )
