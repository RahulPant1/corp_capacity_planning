"""Admin tab — data loading and runtime configuration.

This is the ONLY tab that writes to session state.

Reads:  all ci_* session state keys (for status banner and data preview)
Writes: ci_data_loaded, ci_daily_df, ci_floor_capacity_df, ci_seat_allocation_df,
        ci_headcount_df, ci_prediction_df, ci_buildings_meta, ci_data_source,
        ci_scenario_multipliers

Two data source paths:
  Sample data  — calls get_*_df() from data/ci_sample_data.py, then build_daily_df()
  Upload       — user uploads 4 CSV/Excel files; validated then joined via build_daily_df()

build_daily_df() is the single join point for all 4 datasets. If the schema changes,
update the column constants in data/ci_sample_data.py (COL_*) AND engine/capacity_forecast.py (C_*).

Scenario Adjustment Configuration expander lets admins edit event multipliers at runtime.
Changes are stored in ci_scenario_multipliers for the session only — they reset on page reload.
To make a multiplier permanent, edit DEFAULT_SCENARIO_MULTIPLIERS in config/defaults.py.
"""


def render() -> None:
    import copy
    import streamlit as st
    import pandas as pd
    from data.ci_sample_data import (
        get_floor_capacity_df,
        get_seat_allocation_df,
        get_headcount_df,
        get_prediction_df,
        build_daily_df,
        get_buildings_meta,
        FLOOR_CAPACITY_COLS,
        SEAT_ALLOC_COLS,
        HEADCOUNT_COLS,
        PREDICTION_COLS,
        COL_CITY, COL_BUILDING, COL_FLOOR, COL_LOB, COL_DATE,
    )
    from config.defaults import DEFAULT_SCENARIO_MULTIPLIERS

    # Required column sets for upload validation
    FLOOR_CAP_REQUIRED  = {"City", "Building Name", "Floor", "Total Capacity"}
    SEAT_ALLOC_REQUIRED = {"LOB", "LOB Leader Name", "City", "Building Name", "Floor", "Allocated Seats"}
    HEADCOUNT_REQUIRED  = {"LOB", "Leader", "Headcount"}
    PREDICTION_REQUIRED = {
        "Date", "Day", "City", "Building Name", "Floor", "LOB", "Leader",
        "Holiday Flag", "Optional Holiday Flag", "Optional Holiday Name",
        "US Holiday Flag", "Employee Count Predicted",
    }
    # "Building" is accepted as an alias for "Building Name" in the prediction file
    PREDICTION_BUILDING_ALIASES = {"Building", "Building Name"}

    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        """Rename 'Building' → 'Building Name' and strip whitespace on join keys."""
        if "Building" in df.columns and "Building Name" not in df.columns:
            df = df.rename(columns={"Building": "Building Name"})
        for col in [COL_CITY, COL_BUILDING]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        if COL_FLOOR in df.columns:
            # Keep floor as string for consistent join key
            df[COL_FLOOR] = df[COL_FLOOR].astype(str).str.strip()
        return df

    def _all_datasets_loaded() -> bool:
        return all(st.session_state.get(k) is not None for k in [
            "ci_floor_capacity_df", "ci_seat_allocation_df",
            "ci_headcount_df", "ci_prediction_df",
        ])

    def _join_and_activate() -> None:
        daily_df = build_daily_df(
            floor_cap_df=st.session_state["ci_floor_capacity_df"],
            allocation_df=st.session_state["ci_seat_allocation_df"],
            headcount_df=st.session_state["ci_headcount_df"],
            prediction_df=st.session_state["ci_prediction_df"],
        )
        st.session_state["ci_daily_df"]       = daily_df
        st.session_state["ci_buildings_meta"] = get_buildings_meta(
            st.session_state["ci_floor_capacity_df"]
        )
        st.session_state["ci_data_loaded"] = True

    # ---------------------------------------------------------------------------
    # Header
    # ---------------------------------------------------------------------------
    st.markdown("### ⚙️ Data Management")
    st.caption(
        "Load the four required datasets to activate all views. "
        "All datasets are joined automatically after upload."
    )
    st.divider()

    # ---------------------------------------------------------------------------
    # Source selector
    # ---------------------------------------------------------------------------
    admin_source = st.radio(
        "Data source",
        ["Use Sample Data", "Upload Your Data"],
        horizontal=True,
        key="admin_data_source",
    )
    st.markdown("")

    # ---------------------------------------------------------------------------
    # Status banner
    # ---------------------------------------------------------------------------
    if st.session_state.get("ci_data_loaded"):
        _df: pd.DataFrame = st.session_state["ci_daily_df"]
        _src = st.session_state.get("ci_data_source", "upload")
        n_buildings = _df[COL_BUILDING].nunique()
        n_lobs      = _df[COL_LOB].nunique()
        n_days      = _df[COL_DATE].nunique()
        st.success(
            f"✅ Data active ({_src}) — {n_buildings} buildings · {n_lobs} LOBs · "
            f"{n_days} prediction days · All tabs are ready."
        )
        if st.button("Clear all data", key="admin_clear", type="secondary"):
            for key in (
                "ci_data_loaded", "ci_daily_df", "ci_floor_capacity_df",
                "ci_seat_allocation_df", "ci_headcount_df", "ci_prediction_df",
                "ci_buildings_meta", "ci_data_source",
            ):
                st.session_state[key] = None if key != "ci_data_loaded" else False
            st.rerun()
        st.divider()

    # ---------------------------------------------------------------------------
    # Sample Data
    # ---------------------------------------------------------------------------
    if admin_source == "Use Sample Data":
        st.markdown(
            "**Built-in dataset** — 12 buildings across 4 cities (Bangalore, Hyderabad, Chennai, Manila), "
            "7 LOBs, 2–3 floors per building with realistic multi-LOB floor sharing. "
            "60-day predicted attendance with holiday flags."
        )
        if st.button("Load Sample Data", type="primary", key="admin_load_sample"):
            with st.status("Loading sample data…", expanded=True) as status:
                st.write("Generating Floor Capacity…")
                fc_df = get_floor_capacity_df()
                st.session_state["ci_floor_capacity_df"] = fc_df

                st.write("Generating Seat Allocation…")
                alloc_df = get_seat_allocation_df()
                st.session_state["ci_seat_allocation_df"] = alloc_df

                st.write("Generating Total Headcount…")
                hc_df = get_headcount_df()
                st.session_state["ci_headcount_df"] = hc_df

                st.write("Generating 60-Day Predictions…")
                pred_df = get_prediction_df()
                st.session_state["ci_prediction_df"] = pred_df

                st.write("Joining datasets…")
                _join_and_activate()
                st.session_state["ci_data_source"] = "sample"
                status.update(label="Sample data loaded ✅", state="complete")
            st.rerun()

    # ---------------------------------------------------------------------------
    # Upload Your Data — 4-step flow
    # ---------------------------------------------------------------------------
    else:
        st.markdown(
            "Upload all four datasets below. Each file is validated on upload. "
            "Once all four are loaded, the datasets are joined automatically."
        )
        st.markdown("")

        # ── Dataset 1 — Floor Capacity ─────────────────────────────────────
        with st.expander(
            "📋 Dataset 1 — Floor Capacity"
            + (" ✅" if st.session_state.get("ci_floor_capacity_df") is not None else ""),
            expanded=st.session_state.get("ci_floor_capacity_df") is None,
        ):
            st.caption("Physical seat inventory per floor. One row per floor.")
            col_t, col_u = st.columns([2, 3])
            with col_t:
                st.download_button(
                    "Download template",
                    data=pd.DataFrame(columns=FLOOR_CAPACITY_COLS).to_csv(index=False),
                    file_name="floor_capacity_template.csv",
                    mime="text/csv",
                    key="admin_fc_tmpl",
                )
                st.caption(f"Required columns: {', '.join(sorted(FLOOR_CAP_REQUIRED))}")
            with col_u:
                if st.session_state.get("ci_floor_capacity_df") is not None:
                    fc = st.session_state["ci_floor_capacity_df"]
                    st.success(f"Loaded — {len(fc)} floors across {fc[COL_BUILDING].nunique()} buildings")
                    if st.button("Replace", key="admin_fc_replace", type="secondary"):
                        st.session_state["ci_floor_capacity_df"] = None
                        st.session_state["ci_data_loaded"] = False
                        st.rerun()
                else:
                    uf = st.file_uploader("Upload Floor Capacity (CSV / Excel)", type=["csv", "xlsx"], key="admin_fc_upload")
                    if uf:
                        try:
                            df = pd.read_csv(uf) if uf.name.endswith(".csv") else pd.read_excel(uf)
                            df = _normalize_df(df)
                            missing = FLOOR_CAP_REQUIRED - set(df.columns)
                            if missing:
                                st.error(f"Missing columns: {', '.join(sorted(missing))}")
                            else:
                                st.session_state["ci_floor_capacity_df"] = df
                                st.rerun()
                        except Exception as e:
                            st.error(f"Could not parse file: {e}")

        # ── Dataset 2 — Seat Allocation ────────────────────────────────────
        with st.expander(
            "🪑 Dataset 2 — Seat Allocation"
            + (" ✅" if st.session_state.get("ci_seat_allocation_df") is not None else ""),
            expanded=st.session_state.get("ci_seat_allocation_df") is None,
        ):
            st.caption("Who sits where. Multiple LOBs can share the same floor.")
            col_t, col_u = st.columns([2, 3])
            with col_t:
                st.download_button(
                    "Download template",
                    data=pd.DataFrame(columns=SEAT_ALLOC_COLS).to_csv(index=False),
                    file_name="seat_allocation_template.csv",
                    mime="text/csv",
                    key="admin_alloc_tmpl",
                )
                st.caption(f"Required columns: {', '.join(sorted(SEAT_ALLOC_REQUIRED))}")
            with col_u:
                if st.session_state.get("ci_seat_allocation_df") is not None:
                    al = st.session_state["ci_seat_allocation_df"]
                    st.success(f"Loaded — {len(al)} LOB-floor assignments · {al[COL_LOB].nunique()} LOBs")
                    if st.button("Replace", key="admin_alloc_replace", type="secondary"):
                        st.session_state["ci_seat_allocation_df"] = None
                        st.session_state["ci_data_loaded"] = False
                        st.rerun()
                else:
                    uf = st.file_uploader("Upload Seat Allocation (CSV / Excel)", type=["csv", "xlsx"], key="admin_alloc_upload")
                    if uf:
                        try:
                            df = pd.read_csv(uf) if uf.name.endswith(".csv") else pd.read_excel(uf)
                            df = _normalize_df(df)
                            missing = SEAT_ALLOC_REQUIRED - set(df.columns)
                            if missing:
                                st.error(f"Missing columns: {', '.join(sorted(missing))}")
                            else:
                                st.session_state["ci_seat_allocation_df"] = df
                                st.rerun()
                        except Exception as e:
                            st.error(f"Could not parse file: {e}")

        # ── Dataset 3 — Total Headcount ────────────────────────────────────
        with st.expander(
            "👥 Dataset 3 — Total Headcount"
            + (" ✅" if st.session_state.get("ci_headcount_df") is not None else ""),
            expanded=st.session_state.get("ci_headcount_df") is None,
        ):
            st.caption("LOB-level total headcount (not per floor). One row per LOB.")
            col_t, col_u = st.columns([2, 3])
            with col_t:
                st.download_button(
                    "Download template",
                    data=pd.DataFrame(columns=HEADCOUNT_COLS).to_csv(index=False),
                    file_name="headcount_template.csv",
                    mime="text/csv",
                    key="admin_hc_tmpl",
                )
                st.caption(f"Required columns: {', '.join(sorted(HEADCOUNT_REQUIRED))}")
            with col_u:
                if st.session_state.get("ci_headcount_df") is not None:
                    hc = st.session_state["ci_headcount_df"]
                    st.success(f"Loaded — {len(hc)} LOBs · {int(hc['Headcount'].sum()):,} total headcount")
                    if st.button("Replace", key="admin_hc_replace", type="secondary"):
                        st.session_state["ci_headcount_df"] = None
                        st.session_state["ci_data_loaded"] = False
                        st.rerun()
                else:
                    uf = st.file_uploader("Upload Total Headcount (CSV / Excel)", type=["csv", "xlsx"], key="admin_hc_upload")
                    if uf:
                        try:
                            df = pd.read_csv(uf) if uf.name.endswith(".csv") else pd.read_excel(uf)
                            missing = HEADCOUNT_REQUIRED - set(df.columns)
                            if missing:
                                st.error(f"Missing columns: {', '.join(sorted(missing))}")
                            else:
                                st.session_state["ci_headcount_df"] = df
                                st.rerun()
                        except Exception as e:
                            st.error(f"Could not parse file: {e}")

        # ── Dataset 4 — 60-Day Prediction ─────────────────────────────────
        with st.expander(
            "📈 Dataset 4 — 60-Day Prediction"
            + (" ✅" if st.session_state.get("ci_prediction_df") is not None else ""),
            expanded=st.session_state.get("ci_prediction_df") is None,
        ):
            st.caption(
                "Model output — predicted daily attendance at floor × LOB granularity. "
                "Column 'Building' is accepted as an alias for 'Building Name'."
            )
            col_t, col_u = st.columns([2, 3])
            with col_t:
                st.download_button(
                    "Download template",
                    data=pd.DataFrame(columns=PREDICTION_COLS).to_csv(index=False),
                    file_name="prediction_template.csv",
                    mime="text/csv",
                    key="admin_pred_tmpl",
                )
                st.caption(f"Required columns: {', '.join(sorted(PREDICTION_REQUIRED))}")
            with col_u:
                if st.session_state.get("ci_prediction_df") is not None:
                    pr = st.session_state["ci_prediction_df"]
                    st.success(
                        f"Loaded — {len(pr):,} rows · {pr[COL_DATE].nunique()} days · "
                        f"{pr[COL_LOB].nunique()} LOBs"
                    )
                    if st.button("Replace", key="admin_pred_replace", type="secondary"):
                        st.session_state["ci_prediction_df"] = None
                        st.session_state["ci_data_loaded"] = False
                        st.rerun()
                else:
                    uf = st.file_uploader("Upload 60-Day Prediction (CSV / Excel)", type=["csv", "xlsx"], key="admin_pred_upload")
                    if uf:
                        try:
                            df = pd.read_csv(uf) if uf.name.endswith(".csv") else pd.read_excel(uf)
                            df = _normalize_df(df)
                            # Validate: allow "Building" as alias for "Building Name"
                            effective_cols = set(df.columns)
                            check_cols = (PREDICTION_REQUIRED - {"Building Name"}) | {"Building Name"}
                            missing = check_cols - effective_cols
                            if missing:
                                st.error(f"Missing columns: {', '.join(sorted(missing))}")
                            else:
                                df[COL_DATE] = pd.to_datetime(df[COL_DATE])
                                st.session_state["ci_prediction_df"] = df
                                st.rerun()
                        except Exception as e:
                            st.error(f"Could not parse file: {e}")

        # ── Auto-join when all 4 uploaded ──────────────────────────────────
        if _all_datasets_loaded() and not st.session_state.get("ci_data_loaded"):
            with st.spinner("Joining datasets…"):
                _join_and_activate()
                st.session_state["ci_data_source"] = "upload"
            st.success("All datasets joined — views are now active.")
            st.rerun()

    # ---------------------------------------------------------------------------
    # Data Preview (shown after any successful load)
    # ---------------------------------------------------------------------------
    if st.session_state.get("ci_data_loaded"):
        st.divider()
        st.markdown("### Data Preview")

        daily_df     = st.session_state["ci_daily_df"]
        fc_df        = st.session_state.get("ci_floor_capacity_df")
        alloc_df     = st.session_state.get("ci_seat_allocation_df")
        hc_df        = st.session_state.get("ci_headcount_df")
        pred_df      = st.session_state.get("ci_prediction_df")

        # KPI row
        kp = st.columns(5)
        kp[0].metric("Buildings",     str(daily_df[COL_BUILDING].nunique()))
        kp[1].metric("LOBs",          str(daily_df[COL_LOB].nunique()))
        kp[2].metric("Prediction Days", str(daily_df[COL_DATE].nunique()))
        kp[3].metric("Prediction Rows", f"{len(daily_df):,}")
        total_hc = int(hc_df["Headcount"].sum()) if hc_df is not None else 0
        kp[4].metric("Total Headcount", f"{total_hc:,}")

        tab_fc, tab_al, tab_hc, tab_pr = st.tabs([
            "Floor Capacity", "Seat Allocation", "Headcount", "Predictions (first 50)"
        ])

        with tab_fc:
            if fc_df is not None:
                st.dataframe(fc_df, use_container_width=True, hide_index=True)

        with tab_al:
            if alloc_df is not None:
                st.dataframe(alloc_df, use_container_width=True, hide_index=True)

        with tab_hc:
            if hc_df is not None:
                st.dataframe(hc_df, use_container_width=True, hide_index=True)

        with tab_pr:
            if pred_df is not None:
                st.dataframe(pred_df.head(50), use_container_width=True, hide_index=True)

    # ---------------------------------------------------------------------------
    # Scenario Adjustment Configuration
    # ---------------------------------------------------------------------------
    st.divider()
    with st.expander("⚙️ Scenario Adjustment Configuration", expanded=False):
        st.caption(
            "Edit the event multipliers used in the Scenario Planner. "
            "Changes apply immediately — no data reload required. "
            "Multiplier > 1.0 increases attendance; < 1.0 decreases attendance."
        )

        if "ci_scenario_multipliers" not in st.session_state:
            st.session_state["ci_scenario_multipliers"] = copy.deepcopy(DEFAULT_SCENARIO_MULTIPLIERS)

        current: dict = st.session_state["ci_scenario_multipliers"]
        editor_df = pd.DataFrame([
            {"Event Key": k, "Label": v["label"], "Multiplier": float(v["multiplier"])}
            for k, v in current.items()
        ])

        edited = st.data_editor(
            editor_df,
            num_rows="dynamic",
            column_config={
                "Event Key": st.column_config.TextColumn("Event Key", required=True),
                "Label":     st.column_config.TextColumn("Label", required=True),
                "Multiplier": st.column_config.NumberColumn(
                    "Multiplier", min_value=0.01, max_value=5.0, step=0.05, format="%.2f"
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="admin_mults_editor",
        )

        col_save, col_reset, _ = st.columns([1, 1, 4])
        with col_save:
            if st.button("Save Changes", key="admin_mults_save", type="primary"):
                new_mults = {}
                for _, row in edited.iterrows():
                    raw_key = str(row.get("Event Key", "")).strip()
                    if not raw_key:
                        continue
                    safe_key = raw_key.lower().replace(" ", "_")
                    label    = str(row.get("Label", raw_key)).strip() or raw_key
                    try:
                        mult = float(row.get("Multiplier", 1.0))
                    except (ValueError, TypeError):
                        mult = 1.0
                    new_mults[safe_key] = {"label": label, "multiplier": max(0.01, mult)}
                if new_mults:
                    st.session_state["ci_scenario_multipliers"] = new_mults
                    st.success("Scenario multipliers saved.")
                else:
                    st.warning("No valid rows to save.")
        with col_reset:
            if st.button("Reset to Defaults", key="admin_mults_reset", type="secondary"):
                st.session_state["ci_scenario_multipliers"] = copy.deepcopy(DEFAULT_SCENARIO_MULTIPLIERS)
                st.success("Reset to defaults.")
                st.rerun()
