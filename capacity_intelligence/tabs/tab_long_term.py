"""Long-Term View tab — 6/12-month strategic footfall view."""


def render() -> None:
    import streamlit as st
    import pandas as pd
    from datetime import date
    from engine.capacity_forecast import (
        filter_df,
        compute_long_term_kpis,
        compute_city_capacity_metrics,
        compute_monthly_utilization,
        generate_insights_long_term,
        plot_monthly_forecast_simple,
        plot_building_heatmap,
    )

    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a CSV.")
        return

    daily_df: pd.DataFrame = st.session_state["ci_daily_df"]
    buildings_meta: list = st.session_state["ci_buildings_meta"]
    bldg_id_to_name = {b["building_id"]: b["building_name"] for b in buildings_meta}
    all_cities = sorted(daily_df["city"].unique().tolist())
    all_lobs = sorted(daily_df["lob"].unique().tolist())

    # --- Filters: City | Building | LoB (Country removed) ---
    fl1, fl2, fl3 = st.columns(3)
    with fl1:
        sel_cities = st.multiselect("City", all_cities, key="lt_city")
    with fl2:
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
            key="lt_bldg",
        )
    with fl3:
        sel_lobs = st.multiselect("Line of Business", all_lobs, key="lt_lob")

    filtered = filter_df(
        daily_df,
        buildings=sel_bldgs or None,
        cities=sel_cities or None,
        lobs=sel_lobs or None,
    )

    # --- Horizon toggle ---
    lt_col1, _ = st.columns([2, 6])
    with lt_col1:
        lt_horizon = st.radio(
            "Horizon", [6, 12],
            format_func=lambda x: f"{x} months",
            horizontal=True, key="lt_horizon",
        )

    st.divider()

    # --- KPI cards ---
    lt_kpis = compute_long_term_kpis(filtered, horizon_months=lt_horizon)
    lk1, lk2, lk3, lk4 = st.columns(4)
    lk1.metric("Avg Monthly Footfall", f"{lt_kpis['avg_monthly_footfall']:,}")
    lk2.metric(
        "Avg Capacity Utilization", f"{lt_kpis['avg_util_pct']}%",
        delta="High risk" if lt_kpis["avg_util_pct"] > 85 else None,
        delta_color="inverse" if lt_kpis["avg_util_pct"] > 85 else "off",
    )
    lk3.metric(
        "Surplus Seats", f"{lt_kpis['surplus_seats']:+,}",
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
    col_ins, col_line = st.columns([2, 3])
    with col_ins:
        st.markdown('<p class="section-header">Long-Range Insights</p>', unsafe_allow_html=True)
        for ins in generate_insights_long_term(filtered, horizon_months=lt_horizon):
            st.markdown(f'<div class="insight-box">{ins}</div>', unsafe_allow_html=True)

    with col_line:
        st.plotly_chart(
            plot_monthly_forecast_simple(filtered),
            use_container_width=True, key="lt_monthly_line",
        )

    st.markdown("")

    # --- Row 3: Heatmap ---
    st.markdown('<p class="section-header">Monthly Utilization by Building</p>', unsafe_allow_html=True)
    monthly_util_df = compute_monthly_utilization(filtered)
    if not monthly_util_df.empty:
        today_str = pd.Timestamp(date.today()).to_period("M")
        end_period = today_str + lt_horizon
        monthly_util_df = monthly_util_df[
            monthly_util_df["year_month"].apply(lambda p: today_str <= p <= end_period)
        ]
    st.plotly_chart(
        plot_building_heatmap(monthly_util_df),
        use_container_width=True, key="lt_heatmap",
    )

    # --- Row 4: Capacity metrics table ---
    st.markdown('<p class="section-header">Capacity Metrics by City</p>', unsafe_allow_html=True)
    metrics_df = compute_city_capacity_metrics(filtered, horizon_months=lt_horizon)

    def _style_city_table(df):
        def _color_util(val):
            try:
                v = float(str(val).replace("%", ""))
                if v > 85:
                    return "color: #dc3545; font-weight: bold"
                elif v < 55:
                    return "color: #856404"
            except (ValueError, TypeError):
                pass
            return ""

        def _color_surplus(val):
            v = str(val)
            try:
                n = int(v.replace("+", "").replace("-", ""))
                if v.startswith("+") and n > 0:
                    return "color: #155724"
                elif v.startswith("-"):
                    return "color: #dc3545; font-weight: bold"
            except (ValueError, TypeError):
                pass
            return ""

        s = df.style
        if "Utilization %" in df.columns:
            s = s.map(_color_util, subset=["Utilization %"])
        if "Surplus" in df.columns:
            s = s.map(_color_surplus, subset=["Surplus"])
        return s

    if not metrics_df.empty:
        st.dataframe(_style_city_table(metrics_df), use_container_width=True, height=200)
    else:
        st.info("No data for current selection.")
