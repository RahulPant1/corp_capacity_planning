"""Admin tab — data loading, upload, and scenario adjustment configuration."""


def render() -> None:
    import copy
    import streamlit as st
    import pandas as pd
    from data.ci_sample_data import (
        get_master_df,
        get_footfall_df,
        get_buildings_meta,
        join_master_footfall,
        MASTER_REQUIRED_COLS,
        MASTER_OPTIONAL_COLS,
        FOOTFALL_REQUIRED_COLS,
    )
    from config.defaults import DEFAULT_SCENARIO_MULTIPLIERS

    st.markdown("### ⚙️ Data Management")
    st.caption(
        "Load sample data or upload your own files to activate all views. "
        "Data is split into two files: a static **Building/Tower Master** "
        "and a daily **Footfall Data** file."
    )
    st.divider()

    # ── Source selector ────────────────────────────────────────────────────
    admin_source = st.radio(
        "Data source",
        ["Use Sample Data", "Upload Your Data"],
        horizontal=True,
        key="admin_data_source",
    )
    st.markdown("")

    # ── Status banner ──────────────────────────────────────────────────────
    if st.session_state.get("ci_data_loaded"):
        _df: pd.DataFrame = st.session_state["ci_daily_df"]
        _src = st.session_state.get("ci_data_source", "upload")
        n_buildings = _df["building_id"].nunique()
        n_towers = _df["tower_id"].nunique() if "tower_id" in _df.columns else None
        tower_info = f", {n_towers} towers" if n_towers else ""
        st.success(
            f"✅ Data active ({_src}) — {n_buildings} buildings{tower_info}, "
            f"{_df['date'].nunique()} days · All tabs are ready."
        )
        if st.button("Clear all data", key="admin_clear", type="secondary"):
            for key in (
                "ci_data_loaded", "ci_daily_df", "ci_master_df",
                "ci_footfall_df", "ci_buildings_meta", "ci_data_source",
            ):
                st.session_state[key] = None if key != "ci_data_loaded" else False
            st.rerun()
        st.divider()

    # ── Sample Data ────────────────────────────────────────────────────────
    if admin_source == "Use Sample Data":
        st.markdown(
            "**Built-in dataset** — 27 synthetic towers across 12 buildings in Bangalore, "
            "Hyderabad, Chennai, and Manila. Covers 365 days with realistic day-of-week "
            "patterns and growth trends. ~9,855 rows total."
        )
        if st.button("Load Sample Data", type="primary", key="admin_load_sample"):
            with st.spinner("Generating sample data…"):
                master_df = get_master_df()
                footfall_df = get_footfall_df()
                daily_df = join_master_footfall(master_df, footfall_df)
                st.session_state["ci_master_df"] = master_df
                st.session_state["ci_footfall_df"] = footfall_df
                st.session_state["ci_daily_df"] = daily_df
                st.session_state["ci_buildings_meta"] = get_buildings_meta()
                st.session_state["ci_data_source"] = "sample"
                st.session_state["ci_data_loaded"] = True
            st.rerun()

    # ── Upload Your Data ───────────────────────────────────────────────────
    else:
        st.markdown(
            "Upload two files separately. The Master defines your building/tower "
            "hierarchy and capacities. The Footfall file contains daily attendance counts. "
            "Both are joined on **tower_id** to activate the views."
        )
        st.markdown("")

        # ── Step 1: Building/Tower Master ──────────────────────────────────
        st.markdown("#### Step 1 — Building / Tower Master")
        st.caption("Static reference data: one row per tower. Rarely changes.")

        master_status = st.session_state.get("ci_master_df")

        col_tmpl1, col_up1 = st.columns([2, 3])
        with col_tmpl1:
            master_template = pd.DataFrame(columns=sorted(MASTER_REQUIRED_COLS | MASTER_OPTIONAL_COLS))
            st.download_button(
                "Download Master template",
                data=master_template.to_csv(index=False),
                file_name="building_master_template.csv",
                mime="text/csv",
                use_container_width=True,
                key="admin_master_tmpl_dl",
            )
            st.caption(f"Required: {', '.join(sorted(MASTER_REQUIRED_COLS))}")
            st.caption(f"Optional: {', '.join(sorted(MASTER_OPTIONAL_COLS))}")

        with col_up1:
            if master_status is not None:
                st.success(
                    f"✅ Master loaded — {master_status['tower_id'].nunique()} towers, "
                    f"{master_status['building_id'].nunique()} buildings"
                )
                if st.button("Replace Master", key="admin_replace_master", type="secondary"):
                    st.session_state["ci_master_df"] = None
                    st.session_state["ci_data_loaded"] = False
                    st.session_state["ci_daily_df"] = None
                    st.rerun()
            else:
                uploaded_master = st.file_uploader(
                    "Upload Building/Tower Master CSV",
                    type=["csv"],
                    key="admin_master_upload",
                )
                if uploaded_master is not None:
                    try:
                        mdf = pd.read_csv(uploaded_master)
                        missing = MASTER_REQUIRED_COLS - set(mdf.columns)
                        if missing:
                            st.error(f"Missing columns: {', '.join(sorted(missing))}")
                        else:
                            st.session_state["ci_master_df"] = mdf
                            st.session_state["ci_data_source"] = "upload"
                            st.rerun()
                    except Exception as e:
                        st.error(f"Could not parse file: {e}")

        st.markdown("")

        # ── Step 2: Footfall Data ──────────────────────────────────────────
        st.markdown("#### Step 2 — Footfall Data")
        st.caption(
            "Daily attendance counts. Re-upload any time to replace the current data. "
            "Must match the tower_ids in your Master."
        )

        footfall_status = st.session_state.get("ci_footfall_df")
        master_loaded = st.session_state.get("ci_master_df") is not None

        col_tmpl2, col_up2 = st.columns([2, 3])
        with col_tmpl2:
            footfall_template = pd.DataFrame(columns=sorted(FOOTFALL_REQUIRED_COLS))
            st.download_button(
                "Download Footfall template",
                data=footfall_template.to_csv(index=False),
                file_name="footfall_template.csv",
                mime="text/csv",
                use_container_width=True,
                key="admin_footfall_tmpl_dl",
                disabled=not master_loaded,
            )
            st.caption(f"Required: {', '.join(sorted(FOOTFALL_REQUIRED_COLS))}")

        with col_up2:
            if not master_loaded:
                st.info("Upload the Building/Tower Master first (Step 1).")
            elif footfall_status is not None:
                st.success(
                    f"✅ Footfall loaded — {len(footfall_status):,} rows, "
                    f"{footfall_status['date'].nunique()} days"
                )
                if st.button("Replace Footfall", key="admin_replace_footfall", type="secondary"):
                    st.session_state["ci_footfall_df"] = None
                    st.session_state["ci_data_loaded"] = False
                    st.session_state["ci_daily_df"] = None
                    st.rerun()
            else:
                uploaded_footfall = st.file_uploader(
                    "Upload Footfall Data CSV",
                    type=["csv"],
                    key="admin_footfall_upload",
                )
                if uploaded_footfall is not None:
                    try:
                        fdf = pd.read_csv(uploaded_footfall, parse_dates=["date"])
                        missing = FOOTFALL_REQUIRED_COLS - set(fdf.columns)
                        if missing:
                            st.error(f"Missing columns: {', '.join(sorted(missing))}")
                        else:
                            fdf["date"] = pd.to_datetime(fdf["date"])
                            # Warn about unmatched tower_ids
                            master_towers = set(
                                st.session_state["ci_master_df"]["tower_id"].unique()
                            )
                            unknown = set(fdf["tower_id"].unique()) - master_towers
                            if unknown:
                                st.warning(
                                    f"{len(unknown)} tower_id(s) in footfall not found in Master "
                                    f"and will have no metadata: {', '.join(sorted(unknown)[:5])}"
                                    + (" …" if len(unknown) > 5 else "")
                                )
                            st.session_state["ci_footfall_df"] = fdf
                            # Auto-join when both files are present
                            daily_df = join_master_footfall(
                                st.session_state["ci_master_df"], fdf
                            )
                            meta = (
                                st.session_state["ci_master_df"]
                                .drop_duplicates("building_id")[
                                    ["building_id", "building_name", "city", "lob"]
                                ]
                                .assign(
                                    total_capacity=st.session_state["ci_master_df"]
                                    .groupby("building_id")["capacity"]
                                    .sum()
                                    .values
                                )
                                .to_dict("records")
                            )
                            st.session_state["ci_daily_df"] = daily_df
                            st.session_state["ci_buildings_meta"] = meta
                            st.session_state["ci_data_loaded"] = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Could not parse file: {e}")

    # ── Data Preview ───────────────────────────────────────────────────────
    if st.session_state.get("ci_data_loaded"):
        st.divider()
        st.markdown("### Data Preview")

        prev_df: pd.DataFrame = st.session_state["ci_daily_df"]
        master_df: pd.DataFrame = st.session_state.get("ci_master_df")
        footfall_df: pd.DataFrame = st.session_state.get("ci_footfall_df")

        # KPI metrics
        dp_cols = st.columns(4)
        dp_cols[0].metric("Footfall Rows", f"{len(footfall_df):,}" if footfall_df is not None else f"{len(prev_df):,}")
        dp_cols[1].metric(
            "Date Range",
            f"{prev_df['date'].min().date()} → {prev_df['date'].max().date()}",
        )
        dp_cols[2].metric("Buildings", str(prev_df["building_id"].nunique()))
        dp_cols[3].metric("Towers", str(prev_df["tower_id"].nunique()) if "tower_id" in prev_df.columns else "—")

        # Master summary
        if master_df is not None:
            st.markdown("")
            st.markdown("**Building / Tower Master**")
            master_display = master_df[[
                c for c in
                ["building_id", "building_name", "tower_id", "tower_name", "city", "lob", "floor_count", "capacity"]
                if c in master_df.columns
            ]].rename(columns={
                "building_id": "Bldg ID", "building_name": "Building",
                "tower_id": "Tower ID", "tower_name": "Tower",
                "city": "City", "lob": "LoB",
                "floor_count": "Floors", "capacity": "Capacity",
            })
            st.dataframe(master_display, use_container_width=True, hide_index=True)

        # Footfall sample
        st.markdown("")
        st.markdown("**Footfall Data — first 20 rows**")
        if footfall_df is not None:
            st.dataframe(footfall_df.head(20), use_container_width=True, hide_index=True)
        else:
            st.dataframe(prev_df[["date", "tower_id", "footfall"]].head(20),
                         use_container_width=True, hide_index=True)

    # ── Scenario Adjustment Configuration ─────────────────────────────────
    st.divider()
    with st.expander("⚙️ Scenario Adjustment Configuration", expanded=False):
        st.caption(
            "Edit the event multipliers used in the Scenario Planner. "
            "Changes apply immediately — no data reload required. "
            "Multiplier > 1.0 increases footfall; < 1.0 decreases footfall."
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
                "Event Key": st.column_config.TextColumn(
                    "Event Key",
                    help="Internal identifier (lowercase, underscores). Used by the engine.",
                    required=True,
                ),
                "Label": st.column_config.TextColumn(
                    "Label",
                    help="Human-readable display name shown on the checkbox.",
                    required=True,
                ),
                "Multiplier": st.column_config.NumberColumn(
                    "Multiplier",
                    help="Footfall scaling factor. 1.20 = +20%, 0.70 = −30%.",
                    min_value=0.01,
                    max_value=5.0,
                    step=0.05,
                    format="%.2f",
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
                    label = str(row.get("Label", raw_key)).strip() or raw_key
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
