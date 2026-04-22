"""Scenario Planner tab.

Reads:  st.session_state["ci_data_loaded"], ["ci_daily_df"], ["ci_scenario_multipliers"]
Writes: nothing  (multipliers are written by Admin tab, not here)

Mode A — Event Impact
  Applies multipliers to predicted attendance for a chosen date window and scope.
  Multipliers are loaded from ci_scenario_multipliers (runtime-editable via Admin tab)
  with DEFAULT_SCENARIO_MULTIPLIERS from config/defaults.py as the fallback.
  Formula: adjusted = predicted × mult_1 × mult_2 × … × (1 + custom_pct/100)

Mode B — RTO & Seat Planning
  Computes seats needed from Total Headcount × RTO fraction, where:
    rto_fraction = rto_days / 5   (slider is 1–5 days/week, NOT a percentage)
  Uses Total Headcount (DS3) — never actual attendance — for planning consistency.
  Formula: seats_needed = (HC × rto_fraction) / target_utilization

To add a new event type: edit DEFAULT_SCENARIO_MULTIPLIERS in config/defaults.py,
or use Admin → Scenario Adjustment Configuration at runtime.

To add a Mode C: follow the radio pattern at the top, add an `elif` branch below.
"""


def render() -> None:
    import streamlit as st
    import pandas as pd
    from datetime import date, timedelta
    from engine.capacity_forecast import (
        C_DATE, C_CITY, C_BUILDING, C_LOB, C_PREDICTED, C_CAPACITY,
        filter_df,
        get_data_anchor,
        apply_scenario_adjustments,
        compute_scenario_kpis,
        compute_building_impact_table,
        compute_live_insights,
        plot_scenario_wedge,
        compute_rto_seat_plan,
        compute_policy_kpis,
        plot_rto_seat_plan,
    )
    from engine.scenario_report import generate_scenario_excel_report
    from config.defaults import DEFAULT_SCENARIO_MULTIPLIERS

    if not st.session_state.get("ci_data_loaded", False):
        st.info("No data loaded. Go to the **⚙️ Admin** tab to load sample data or upload files.")
        return

    daily_df: pd.DataFrame = st.session_state["ci_daily_df"]
    all_lobs  = sorted(daily_df[C_LOB].unique().tolist())
    all_bldgs = sorted(daily_df[C_BUILDING].unique().tolist())

    mults_config: dict = st.session_state.get("ci_scenario_multipliers", DEFAULT_SCENARIO_MULTIPLIERS)
    flat_mults = {k: v["multiplier"] for k, v in mults_config.items()}

    # ── Mode selector ──────────────────────────────────────────────────────
    sp_mode = st.radio(
        "Scenario mode",
        ["Event Impact", "RTO & Seat Planning"],
        horizontal=True,
        key="sp_mode",
        help=(
            "Event Impact: model a specific disruption or event over a date window. "
            "RTO & Seat Planning: compute seat needs from HC × RTO mandate %."
        ),
    )
    # ===========================================================================
    # MODE A — EVENT IMPACT
    # ===========================================================================
    if sp_mode == "Event Impact":
        col_ctrl, col_impact = st.columns([3, 7])

        with col_ctrl:
            st.markdown('<p class="section-header">Event Controls</p>', unsafe_allow_html=True)

            sel_lobs_a  = st.multiselect("Filter: Line of Business", all_lobs, key="sp_lob_a")
            sel_bldgs_a = st.multiselect("Filter: Building", all_bldgs, key="sp_bldg_a")


            st.markdown("**Adjustment Scope**")
            st.caption("Apply adjustments to the whole portfolio or target specific buildings / LOBs.")
            scope_choice = st.radio(
                "Apply to",
                ["Portfolio-wide", "Specific Buildings", "Specific LoB"],
                horizontal=False,
                key="sp_scope_mode",
            )
            if scope_choice == "Specific Buildings":
                scope_vals    = st.multiselect("Select buildings", all_bldgs, key="sp_scope_bldgs")
                adj_scope     = "buildings"
                adj_scope_values = scope_vals or []
            elif scope_choice == "Specific LoB":
                scope_vals    = st.multiselect("Select LOBs", all_lobs, key="sp_scope_lob")
                adj_scope     = "lob"
                adj_scope_values = scope_vals or []
            else:
                adj_scope        = "all"
                adj_scope_values = []

            st.markdown("**Event Period**")
            # Use data anchor so presets work on historical/future-dated datasets too
            today = get_data_anchor(daily_df)
            data_end = daily_df[C_DATE].max().date()
            period_preset = st.radio(
                "Planning window",
                ["Next Week", "Next 2 Weeks", "Next Month", "Custom"],
                horizontal=True,
                index=0,
                key="sp_period_preset",
            )
            if period_preset == "Next Week":
                dr_start, dr_end = today + timedelta(1), min(today + timedelta(7), data_end)
            elif period_preset == "Next 2 Weeks":
                dr_start, dr_end = today + timedelta(1), min(today + timedelta(14), data_end)
            elif period_preset == "Next Month":
                dr_start, dr_end = today + timedelta(1), min(today + timedelta(30), data_end)
            else:
                cr = st.date_input(
                    "Date range",
                    value=(today + timedelta(7), min(today + timedelta(21), data_end)),
                    min_value=today,
                    max_value=data_end,
                    key="sp_daterange_a",
                )
                if isinstance(cr, (list, tuple)) and len(cr) == 2:
                    dr_start, dr_end = cr[0], cr[1]
                else:
                    dr_start, dr_end = today + timedelta(7), today + timedelta(21)

            if period_preset != "Custom":
                n_days = (dr_end - dr_start).days + 1
                st.caption(f"📅 {dr_start.strftime('%b %d')} → {dr_end.strftime('%b %d, %Y')} ({n_days} days)")

            st.markdown("**Built-in Adjustments**")
            st.caption("Multipliers configurable via ⚙️ Admin.")

            corporate_keys   = [k for k in mults_config if k in ("townhall", "leadership_visit")]
            disruption_keys  = [k for k in mults_config if k in ("weather_alert", "traffic_disruption")]
            calendar_keys    = [k for k in mults_config if k in ("mandatory_holiday", "optional_holiday", "us_holiday")]
            other_keys       = [k for k in mults_config
                                if k not in corporate_keys + disruption_keys + calendar_keys]

            def _checkbox_group(label, keys, prefix):
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
            adj_checks.update(_checkbox_group("Corporate Events",      corporate_keys,  "corp"))
            adj_checks.update(_checkbox_group("External Disruptions",  disruption_keys, "dis"))
            adj_checks.update(_checkbox_group("Calendar Anomalies",    calendar_keys,   "cal"))
            adj_checks.update(_checkbox_group("Other",                 other_keys,      "oth"))

            st.markdown("**Custom Factor**")
            custom_pct = st.number_input(
                "% adjustment (+ = more, − = less)",
                min_value=-100.0, max_value=200.0, value=0.0, step=5.0,
                key="sp_custom",
            )

        # Compute
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
            st.markdown('<p class="section-header">Event Impact</p>', unsafe_allow_html=True)

            sp_kpis   = compute_scenario_kpis(baseline_a, scenario_a, (dr_start, dr_end))
            daily_delta = sp_kpis["scenario_avg_daily"] - sp_kpis["baseline_avg_daily"]
            wkdays    = sp_kpis.get("window_weekdays", sp_kpis["window_days"])

            sk1, sk2, sk3 = st.columns(3)
            sk1.metric("Baseline Avg Daily", f"{sp_kpis['baseline_avg_daily']:,} seats/day")
            sk2.metric(
                "Scenario Avg Daily",
                f"{sp_kpis['scenario_avg_daily']:,} seats/day",
                delta=f"{daily_delta:+,} seats/day" if daily_delta != 0 else None,
                delta_color="normal" if daily_delta >= 0 else "inverse",
            )
            sk3.metric("Event Window", f"{sp_kpis['window_days']} days ({wkdays} weekdays)")

            if sp_kpis["delta"] != 0:
                d = sp_kpis["delta"]
                st.caption(
                    f"Total impact over window: **{d:+,} person-days** vs baseline"
                )
            else:
                st.caption("No adjustment applied — select an event or set a custom factor to see impact.")

            sp_horizon = min(60, (dr_end - today).days + 20)
            st.plotly_chart(
                plot_scenario_wedge(baseline_a, scenario_a, (dr_start, dr_end), horizon_days=sp_horizon),
                use_container_width=True, key="sp_wedge",
            )

            st.markdown('<p class="section-header">Impact by Building</p>', unsafe_allow_html=True)
            impact_df = compute_building_impact_table(baseline_a, scenario_a, (dr_start, dr_end))

            def _style_diff(df):
                def _c(v):
                    try:
                        fv = float(v)
                        if fv > 0: return "color:#155724;font-weight:bold"
                        if fv < 0: return "color:#dc3545;font-weight:bold"
                    except (ValueError, TypeError):
                        pass
                    return ""
                return df.style.map(_c, subset=["Difference"])

            if not impact_df.empty:
                st.dataframe(_style_diff(impact_df), use_container_width=True, height=220)
            else:
                st.info("No buildings match the current filter.")

            with st.expander("📊 Live Impact Insights", expanded=True):
                live_insights = compute_live_insights(
                    baseline_a, scenario_a, (dr_start, dr_end),
                    scope=adj_scope, scope_values=adj_scope_values,
                )
                for ins in live_insights:
                    st.markdown(f'<div class="insight-box">{ins}</div>', unsafe_allow_html=True)


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
            )

    # ===========================================================================
    # MODE B — RTO & SEAT PLANNING
    # ===========================================================================
    else:
        col_ctrl, col_result = st.columns([3, 7])

        with col_ctrl:
            st.markdown('<p class="section-header">Planning Controls</p>', unsafe_allow_html=True)

            sel_lobs_b  = st.multiselect("Filter: Line of Business", all_lobs, key="sp_lob_b")
            sel_bldgs_b = st.multiselect("Filter: Building", all_bldgs, key="sp_bldg_b")


            st.markdown("**RTO Mandate**")
            rto_days = st.slider(
                "Days per week in office",
                min_value=1, max_value=5, value=3, step=1,
                key="sp_rto_days",
                help="How many days per week each LOB is expected to be in office. 1 = one day/week, 5 = full week.",
            )
            rto_fraction = rto_days / 5
            st.caption(
                f"**{rto_days} day{'s' if rto_days > 1 else ''}/week** → "
                f"{rto_fraction*100:.0f}% of total headcount expected in office on any given day."
            )


            st.markdown("**Seat Planning Target**")
            target_util_pct = st.slider(
                "Target seat utilization %",
                min_value=50, max_value=95, value=80, step=5,
                key="sp_target_util",
                help="Planning buffer. Seats needed = Expected demand / Target%. Lower % = more buffer.",
            )
            st.caption(
                f"Seats needed = Expected demand ÷ {target_util_pct}%. "
                f"At {target_util_pct}% target, you build in a {100-target_util_pct}% headroom buffer."
            )


            st.info(
                f"**Formula:**  \n"
                f"Expected demand = Total HC × ({rto_days}/5 days) = Total HC × {rto_fraction*100:.0f}%  \n"
                f"Seats needed = Expected demand ÷ {target_util_pct}%  \n"
                f"Seat gap = Allocated seats − Seats needed",
                icon="📐",
            )

        filtered_b = filter_df(daily_df, buildings=sel_bldgs_b or None, lobs=sel_lobs_b or None)

        with col_result:
            st.markdown('<p class="section-header">Seat Planning Results</p>', unsafe_allow_html=True)

            kpis_b = compute_policy_kpis(filtered_b, rto_fraction, target_util_pct / 100)

            pk1, pk2, pk3, pk4 = st.columns(4)
            pk1.metric("Total Headcount",    f"{kpis_b['total_hc']:,}")
            pk2.metric(
                "Expected Daily Demand",
                f"{kpis_b['expected_demand']:,} seats",
                delta=f"{rto_days} day{'s' if rto_days > 1 else ''}/week RTO",
                delta_color="off",
            )
            pk3.metric("Total Allocated",    f"{kpis_b['total_allocated']:,} seats")
            pk4.metric(
                "Portfolio Seat Gap",
                f"{kpis_b['portfolio_gap']:+,}",
                delta="Surplus" if kpis_b["portfolio_gap"] >= 0 else "Deficit",
                delta_color="off" if kpis_b["portfolio_gap"] >= 0 else "inverse",
            )



            plan_df = compute_rto_seat_plan(filtered_b, rto_fraction, target_util_pct / 100)
            if not plan_df.empty:
                st.plotly_chart(
                    plot_rto_seat_plan(plan_df),
                    use_container_width=True, key="sp_rto_chart",
                )

                st.markdown('<p class="section-header">Seat Gap by LOB</p>', unsafe_allow_html=True)

                def _style_plan(df):
                    def _c(v):
                        try:
                            return "color:#dc3545;font-weight:bold" if float(v) < 0 else "color:#155724;font-weight:bold"
                        except (ValueError, TypeError):
                            return ""
                    return df.style.map(_c, subset=["Seat Gap"])

                st.dataframe(
                    _style_plan(plan_df),
                    use_container_width=True, hide_index=True, height=280,
                )

                st.caption(
                    "Seat Gap = Allocated Seats − Seats Needed. "
                    "Negative = deficit; increase allocation or lower RTO mandate."
                )

                # Sensitivity callout
                deficits = plan_df[plan_df["Seat Gap"] < 0]
                if not deficits.empty:
                    lob_list = ", ".join(deficits["LOB"].tolist())
                    st.warning(
                        f"**{len(deficits)} LOB(s) have a seat deficit at {rto_days} day{'s' if rto_days > 1 else ''}/week RTO / "
                        f"{target_util_pct}% target:** {lob_list}. "
                        "Consider increasing allocated seats or reducing the RTO mandate."
                    )
                else:
                    st.success(
                        f"All LOBs have sufficient allocated seats at {rto_days} day{'s' if rto_days > 1 else ''}/week RTO / "
                        f"{target_util_pct}% target utilization."
                    )

                # Download
    
                st.markdown('<p class="section-header">Download Report</p>', unsafe_allow_html=True)
                insights_b = [
                    f"RTO Mandate: {rto_days} day{'s' if rto_days > 1 else ''}/week ({rto_fraction*100:.0f}% of total HC in office daily)",
                    f"Target utilization: {target_util_pct}%",
                    f"Total headcount: {kpis_b['total_hc']:,}",
                    f"Expected daily demand: {kpis_b['expected_demand']:,} seats",
                    f"Total allocated seats: {kpis_b['total_allocated']:,}",
                    f"Portfolio seat gap: {kpis_b['portfolio_gap']:+,}",
                ]
                kpis_for_report = {
                    "baseline_avg_daily": kpis_b["expected_demand"],
                    "scenario_avg_daily": kpis_b["total_seats_needed"],
                    "window_days": 0,
                    "window_weekdays": 0,
                }
                xlsx_bytes_b = generate_scenario_excel_report(
                    baseline_df=filtered_b,
                    scenario_df=filtered_b,
                    date_range=(filtered_b[C_DATE].min().date(), filtered_b[C_DATE].max().date()),
                    scenario_kpis=kpis_for_report,
                    building_impact_df=plan_df,
                    live_insights=insights_b,
                    mode="RTO & Seat Planning",
                    mode_params={
                        "RTO Mandate":             f"{rto_days} day{'s' if rto_days > 1 else ''}/week ({rto_fraction*100:.0f}% of HC)",
                        "Target Utilization %":    f"{target_util_pct}%",
                        "Expected Daily Demand":   kpis_b["expected_demand"],
                        "Total Seats Needed":      kpis_b["total_seats_needed"],
                        "Portfolio Seat Gap":      kpis_b["portfolio_gap"],
                    },
                )
                st.download_button(
                    label="⬇ Download Seat Plan (.xlsx)",
                    data=xlsx_bytes_b,
                    file_name=f"seat_plan_rto{rto_days}d_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="sp_dl_xlsx_b",
                )
            else:
                st.info("Headcount or allocation data not available. Load data via the Admin tab.")
