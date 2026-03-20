"""Scenario Planner tab — Event Impact (Mode A) and Policy Simulation (Mode B)."""


def render() -> None:
    import streamlit as st
    import pandas as pd
    from datetime import date, timedelta
    from engine.capacity_forecast import (
        filter_df,
        apply_scenario_adjustments,
        compute_scenario_kpis,
        compute_building_impact_table,
        compute_live_insights,
        plot_scenario_wedge,
        simulate_rto_policy,
        compute_seat_gap_by_building,
        compute_policy_kpis,
        plot_rto_comparison,
        BASELINE_RTO_DAYS,
    )
    from engine.scenario_report import generate_scenario_excel_report
    from config.defaults import DEFAULT_SCENARIO_MULTIPLIERS

    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload a CSV.")
        return

    daily_df: pd.DataFrame = st.session_state["ci_daily_df"]
    buildings_meta: list = st.session_state["ci_buildings_meta"]
    bldg_id_to_name = {b["building_id"]: b["building_name"] for b in buildings_meta}
    all_lobs = sorted(daily_df["lob"].unique().tolist())

    # Read configurable multipliers from session state (set in Admin tab)
    mults_config: dict = st.session_state.get("ci_scenario_multipliers", DEFAULT_SCENARIO_MULTIPLIERS)
    flat_mults = {k: v["multiplier"] for k, v in mults_config.items()}

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

    # ===========================================================================
    # MODE A — EVENT IMPACT
    # ===========================================================================
    if sp_mode == "Event Impact":
        col_controls, col_impact = st.columns([3, 7])

        with col_controls:
            st.markdown("### Event Controls")

            sel_lobs_a = st.multiselect("Filter: Line of Business", all_lobs, key="sp_lob_a")
            sel_bldgs_a = st.multiselect(
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
            st.caption("Select when the event occurs. Only footfall in this window is adjusted.")

            today = date.today()
            period_preset = st.radio(
                "Planning window",
                ["Next Week", "Next 2 Weeks", "Next Month", "Next Quarter", "Custom"],
                horizontal=True,
                index=0,
                key="sp_period_preset",
            )

            if period_preset == "Next Week":
                dr_start = today + timedelta(days=1)
                dr_end   = today + timedelta(days=7)
            elif period_preset == "Next 2 Weeks":
                dr_start = today + timedelta(days=1)
                dr_end   = today + timedelta(days=14)
            elif period_preset == "Next Month":
                dr_start = today + timedelta(days=1)
                dr_end   = today + timedelta(days=30)
            elif period_preset == "Next Quarter":
                dr_start = today + timedelta(days=1)
                dr_end   = today + timedelta(days=90)
            else:  # Custom
                custom_range = st.date_input(
                    "Select date range",
                    value=(today + timedelta(days=7), today + timedelta(days=21)),
                    min_value=today,
                    max_value=today + timedelta(days=365),
                    key="sp_daterange_a",
                )
                if isinstance(custom_range, (list, tuple)) and len(custom_range) == 2:
                    dr_start, dr_end = custom_range[0], custom_range[1]
                else:
                    dr_start = today + timedelta(days=7)
                    dr_end   = today + timedelta(days=21)

            if period_preset != "Custom":
                n_days = (dr_end - dr_start).days + 1
                st.caption(f"📅 {dr_start.strftime('%b %d')} → {dr_end.strftime('%b %d, %Y')} ({n_days} days)")

            st.markdown("")
            st.markdown("**Built-in Adjustments**")
            st.caption("Multipliers are configurable via the ⚙️ Admin tab.")

            # --- Dynamic checkboxes generated from configurable multipliers ---
            # Group into categories by key name pattern
            corporate_keys = [k for k in mults_config if k in ("townhall", "leadership_visit")]
            disruption_keys = [k for k in mults_config if k in ("weather_alert", "traffic_disruption")]
            calendar_keys = [k for k in mults_config if k in ("mandatory_holiday", "optional_holiday", "us_holiday")]
            other_keys = [k for k in mults_config
                          if k not in corporate_keys + disruption_keys + calendar_keys]

            def _checkbox_group(label: str, keys: list, prefix: str) -> dict:
                if not keys:
                    return {}
                st.markdown(f'<p class="section-header">{label}</p>', unsafe_allow_html=True)
                result = {}
                for key in keys:
                    cfg = mults_config[key]
                    pct = (cfg["multiplier"] - 1.0) * 100
                    sign = "+" if pct >= 0 else ""
                    result[key] = st.checkbox(
                        f"{cfg['label']}  ({sign}{pct:.0f}%)",
                        key=f"sp_{prefix}_{key}",
                    )
                return result

            adj_checks: dict = {}
            adj_checks.update(_checkbox_group("Corporate Events", corporate_keys, "corp"))
            adj_checks.update(_checkbox_group("External Disruptions", disruption_keys, "dis"))
            adj_checks.update(_checkbox_group("Calendar Anomalies", calendar_keys, "cal"))
            adj_checks.update(_checkbox_group("Other", other_keys, "oth"))

            st.markdown("")
            st.markdown("**Custom Factor**")
            custom_pct = st.number_input(
                "% adjustment (+ = more footfall, − = less)",
                min_value=-100.0, max_value=200.0, value=0.0, step=5.0,
                key="sp_custom",
            )

        # Compute baseline + scenario
        baseline_a = filter_df(daily_df, buildings=sel_bldgs_a or None, lobs=sel_lobs_a or None)
        scenario_a = apply_scenario_adjustments(
            baseline_a,
            date_range=(dr_start, dr_end),
            adjustments=adj_checks,
            custom_factor_pct=custom_pct,
            scope=adj_scope,
            scope_values=adj_scope_values,
            scenario_multipliers=flat_mults,
        )

        with col_impact:
            st.markdown("### Event Impact")

            sp_kpis = compute_scenario_kpis(baseline_a, scenario_a, (dr_start, dr_end))
            daily_delta = sp_kpis["scenario_avg_daily"] - sp_kpis["baseline_avg_daily"]
            delta_val = sp_kpis["delta"]
            wkdays = sp_kpis.get("window_weekdays", sp_kpis["window_days"])

            sk1, sk2, sk3 = st.columns(3)
            sk1.metric("Baseline Avg Daily", f"{sp_kpis['baseline_avg_daily']:,} seats/day")
            sk2.metric(
                "Scenario Avg Daily",
                f"{sp_kpis['scenario_avg_daily']:,} seats/day",
                delta=f"{daily_delta:+,} seats/day" if daily_delta != 0 else None,
                delta_color="normal" if daily_delta >= 0 else "inverse",
            )
            sk3.metric("Event Window", f"{sp_kpis['window_days']} days")

            if delta_val != 0:
                direction = f"+{delta_val:,}" if delta_val > 0 else f"{delta_val:,}"
                st.caption(
                    f"Event window: {sp_kpis['window_days']} calendar days ({wkdays} weekdays) · "
                    f"Total impact: **{direction} person-days** vs baseline"
                )
            else:
                st.caption(
                    f"Event window: {sp_kpis['window_days']} calendar days ({wkdays} weekdays) · "
                    "No adjustment applied — select an event or set a custom factor to see impact."
                )

            sp_horizon = min(90, (dr_end - date.today()).days + 30)
            st.plotly_chart(
                plot_scenario_wedge(baseline_a, scenario_a, (dr_start, dr_end), horizon_days=sp_horizon),
                use_container_width=True, key="sp_wedge",
            )

            st.markdown('<p class="section-header">Impact by Building</p>', unsafe_allow_html=True)
            impact_df = compute_building_impact_table(baseline_a, scenario_a, (dr_start, dr_end))

            def _style_diff(df):
                def _c(val):
                    try:
                        v = float(val)
                        if v > 0:
                            return "color: #155724; font-weight: bold"
                        elif v < 0:
                            return "color: #dc3545; font-weight: bold"
                    except (ValueError, TypeError):
                        pass
                    return ""
                return df.style.map(_c, subset=["Difference"])

            if not impact_df.empty:
                st.dataframe(_style_diff(impact_df), use_container_width=True, height=220)
            else:
                st.info("No buildings match the current filter.")

            # Live Impact Insights
            with st.expander("📊 Live Impact Insights", expanded=True):
                live_insights = compute_live_insights(
                    baseline_a, scenario_a, (dr_start, dr_end),
                    scope=adj_scope, scope_values=adj_scope_values,
                )
                for ins in live_insights:
                    st.markdown(f'<div class="insight-box">{ins}</div>', unsafe_allow_html=True)

            # --- Download Impact Report ---
            st.markdown("")
            st.markdown('<p class="section-header">Download Report</p>', unsafe_allow_html=True)
            xlsx_bytes = generate_scenario_excel_report(
                baseline_df=baseline_a,
                scenario_df=scenario_a,
                date_range=(dr_start, dr_end),
                scenario_kpis=sp_kpis,
                building_impact_df=impact_df,
                live_insights=live_insights,
                mode="Event Impact",
            )
            st.download_button(
                label="⬇ Download Impact Report (.xlsx)",
                data=xlsx_bytes,
                file_name=f"scenario_impact_{dr_start}_{dr_end}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="sp_dl_xlsx_a",
                use_container_width=False,
            )

    # ===========================================================================
    # MODE B — POLICY SIMULATION
    # ===========================================================================
    else:
        col_policy, col_policy_impact = st.columns([3, 7])

        with col_policy:
            st.markdown("### Policy Controls")

            sel_lobs_b = st.multiselect("Filter: Line of Business", all_lobs, key="sp_lob_b")
            sel_bldgs_b = st.multiselect(
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
            if delta_rto > 0:
                rto_caption = (
                    f"Baseline is {BASELINE_RTO_DAYS} days/week. "
                    f"+{delta_rto:.1f} days → footfall increases ~{delta_rto/BASELINE_RTO_DAYS*100:.0f}%"
                )
            elif delta_rto < 0:
                rto_caption = (
                    f"Baseline is {BASELINE_RTO_DAYS} days/week. "
                    f"{delta_rto:.1f} days → footfall decreases ~{abs(delta_rto)/BASELINE_RTO_DAYS*100:.0f}%"
                )
            else:
                rto_caption = f"Baseline is {BASELINE_RTO_DAYS} days/week. No change from baseline."
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

        baseline_b = filter_df(daily_df, buildings=sel_bldgs_b or None, lobs=sel_lobs_b or None)
        policy_df = simulate_rto_policy(baseline_b, new_rto_days=new_rto)

        with col_policy_impact:
            st.markdown("### Policy Impact")

            pb_kpis = compute_policy_kpis(
                baseline_b, policy_df,
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
                "Portfolio Seat Gap", f"{pb_kpis['portfolio_gap']:+,}",
                delta="Surplus" if pb_kpis["portfolio_gap"] >= 0 else "Deficit",
                delta_color="off" if pb_kpis["portfolio_gap"] >= 0 else "inverse",
            )
            pk4.metric("Total Capacity", f"{pb_kpis['total_capacity']:,}")

            st.markdown("")
            st.plotly_chart(
                plot_rto_comparison(baseline_b, policy_df),
                use_container_width=True, key="sp_rto_chart",
            )

            st.markdown('<p class="section-header">Seat Gap by Building</p>', unsafe_allow_html=True)
            gap_df = compute_seat_gap_by_building(
                policy_df,
                target_utilization=target_util_pct / 100.0,
                horizon_days=pb_horizon_days,
            )

            def _style_gap(df):
                def _c(val):
                    try:
                        v = float(val)
                        if v > 0:
                            return "color: #155724; font-weight: bold"
                        elif v < 0:
                            return "color: #dc3545; font-weight: bold"
                    except (ValueError, TypeError):
                        pass
                    return ""
                return df.style.map(_c, subset=["Surplus / Deficit"])

            if not gap_df.empty:
                st.dataframe(_style_gap(gap_df), use_container_width=True, height=280)
            else:
                st.info("No buildings match the current filter.")

            # --- Download Impact Report ---
            st.markdown("")
            st.markdown('<p class="section-header">Download Report</p>', unsafe_allow_html=True)
            pb_insights = [
                f"RTO Policy: {new_rto} days/week (baseline: {BASELINE_RTO_DAYS} days/week)",
                f"Avg daily demand change: {pb_kpis['demand_delta']:+,} seats/day",
                f"Portfolio seat gap: {pb_kpis['portfolio_gap']:+,} seats",
                f"Target utilization: {target_util_pct}%",
                f"Horizon: {pb_horizon_opt}",
            ]
            pb_kpis_for_report = {
                "baseline_avg_daily": pb_kpis["base_demand"],
                "scenario_avg_daily": pb_kpis["policy_demand"],
                "window_days": pb_horizon_days,
                "window_weekdays": pb_horizon_days * 5 // 7,
            }
            xlsx_bytes_b = generate_scenario_excel_report(
                baseline_df=baseline_b,
                scenario_df=policy_df,
                date_range=(date.today(), date.today() + timedelta(days=pb_horizon_days)),
                scenario_kpis=pb_kpis_for_report,
                building_impact_df=gap_df,
                live_insights=pb_insights,
                mode="Policy Simulation",
                mode_params={
                    "RTO Days (new)": new_rto,
                    "RTO Days (baseline)": BASELINE_RTO_DAYS,
                    "Target Utilization": f"{target_util_pct}%",
                    "Horizon": pb_horizon_opt,
                },
            )
            st.download_button(
                label="⬇ Download Impact Report (.xlsx)",
                data=xlsx_bytes_b,
                file_name=f"policy_simulation_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="sp_dl_xlsx_b",
                use_container_width=False,
            )
