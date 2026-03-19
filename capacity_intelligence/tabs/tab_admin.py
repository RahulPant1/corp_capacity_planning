"""Admin tab — data loading, upload, and scenario adjustment configuration."""


def render() -> None:
    import copy
    import streamlit as st
    import pandas as pd
    from data.ci_sample_data import (
        generate_daily_footfall,
        get_buildings_meta,
        REQUIRED_COLS,
        OPTIONAL_COLS,
    )
    from config.defaults import DEFAULT_SCENARIO_MULTIPLIERS

    st.markdown("### ⚙️ Data Management")
    st.caption("Load sample data or upload your own footfall CSV to activate all views.")
    st.divider()

    # --- Source selector ---
    admin_source = st.radio(
        "Data source",
        ["Use Sample Data", "Upload your CSV"],
        horizontal=True,
        key="admin_data_source",
    )
    st.markdown("")

    # --- Status banner ---
    if st.session_state.get("ci_data_loaded"):
        _df: pd.DataFrame = st.session_state["ci_daily_df"]
        _src = "sample" if st.session_state.get("ci_data_source") == "sample" else "uploaded CSV"
        n_buildings = _df["building_id"].nunique()
        n_towers = _df["tower_id"].nunique() if "tower_id" in _df.columns else None
        tower_info = f", {n_towers} towers" if n_towers else ""
        st.success(
            f"✅ Data active ({_src}) — {n_buildings} buildings{tower_info}, "
            f"{_df['date'].nunique()} days · All tabs are ready."
        )
        if st.button("Clear data", key="admin_clear", type="secondary"):
            for key in ("ci_data_loaded", "ci_daily_df", "ci_buildings_meta", "ci_data_source"):
                st.session_state[key] = None if key != "ci_data_loaded" else False
            st.rerun()
        st.divider()

    # --- Load Sample Data ---
    if admin_source == "Use Sample Data":
        st.markdown(
            "**Built-in dataset** — 27 synthetic towers across 12 buildings in Bangalore, Hyderabad, "
            "Chennai, and Manila. Covers 365 days with realistic day-of-week patterns and growth trends. "
            "~9,855 rows total."
        )
        if st.button("Load Sample Data", type="primary", key="admin_load_sample"):
            with st.spinner("Generating sample data…"):
                st.session_state["ci_daily_df"] = generate_daily_footfall()
                st.session_state["ci_buildings_meta"] = get_buildings_meta()
                st.session_state["ci_data_source"] = "sample"
                st.session_state["ci_data_loaded"] = True
            st.rerun()

    # --- Upload CSV ---
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
            st.caption(f"Required: {', '.join(sorted(REQUIRED_COLS))}")
            st.caption(f"Optional: {', '.join(sorted(OPTIONAL_COLS))}")
        with col_up:
            uploaded = st.file_uploader("Upload footfall CSV", type=["csv"], key="admin_upload")
            if uploaded is not None:
                try:
                    user_df = pd.read_csv(uploaded, parse_dates=["date"])
                    missing = REQUIRED_COLS - set(user_df.columns)
                    if missing:
                        st.error(f"Missing columns: {', '.join(sorted(missing))}")
                    elif not st.session_state.get("ci_data_loaded"):
                        user_df["date"] = pd.to_datetime(user_df["date"])
                        # Build buildings meta (country is optional)
                        bldg_cols = ["building_id", "building_name", "city", "lob", "capacity"]
                        if "country" in user_df.columns:
                            bldg_cols.insert(3, "country")
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
                        st.rerun()
                except Exception as e:
                    st.error(f"Could not parse file: {e}")

    # --- Data Preview ---
    if st.session_state.get("ci_data_loaded"):
        st.divider()
        st.markdown("### Data Preview")

        prev_df: pd.DataFrame = st.session_state["ci_daily_df"]
        dp_cols = st.columns(4 if "tower_id" in prev_df.columns else 3)
        dp_cols[0].metric("Total Records", f"{len(prev_df):,}")
        dp_cols[1].metric(
            "Date Range",
            f"{prev_df['date'].min().date()} → {prev_df['date'].max().date()}",
        )
        dp_cols[2].metric("Buildings", str(prev_df["building_id"].nunique()))
        if "tower_id" in prev_df.columns:
            dp_cols[3].metric("Towers", str(prev_df["tower_id"].nunique()))

        st.markdown("")
        st.markdown("**Sample rows (first 20)**")
        st.dataframe(prev_df.head(20), use_container_width=True)

        # Building/tower summary
        st.markdown("")
        if "tower_id" in prev_df.columns:
            st.markdown("**Towers in dataset**")
            summary = (
                prev_df.groupby(["building_id", "building_name", "tower_id", "tower_name", "city", "lob"])
                .agg(
                    capacity=("capacity", "first"),
                    floor_count=("floor_count", "first") if "floor_count" in prev_df.columns else ("capacity", "count"),
                    days=("date", "nunique"),
                    avg_util=("utilization_pct", "mean"),
                )
                .reset_index()
                .rename(columns={
                    "building_id": "Bldg ID", "building_name": "Building",
                    "tower_id": "Tower ID", "tower_name": "Tower",
                    "city": "City", "lob": "LoB",
                    "capacity": "Capacity", "floor_count": "Floors",
                    "days": "Days", "avg_util": "Avg Util %",
                })
            )
        else:
            st.markdown("**Buildings in dataset**")
            grp_cols = ["building_id", "building_name", "city", "lob"]
            if "country" in prev_df.columns:
                grp_cols.insert(3, "country")
            summary = (
                prev_df.groupby(grp_cols)
                .agg(capacity=("capacity", "first"), days=("date", "nunique"), avg_util=("utilization_pct", "mean"))
                .reset_index()
                .rename(columns={
                    "building_id": "ID", "building_name": "Building",
                    "city": "City", "lob": "LoB",
                    "capacity": "Capacity", "days": "Days", "avg_util": "Avg Util %",
                })
            )

        summary["Avg Util %"] = (summary["Avg Util %"] * 100).round(1).astype(str) + "%"
        st.dataframe(summary, use_container_width=True)

    # ===========================================================================
    # Scenario Adjustment Configuration
    # ===========================================================================
    st.divider()
    with st.expander("⚙️ Scenario Adjustment Configuration", expanded=False):
        st.caption(
            "Edit the event multipliers used in the Scenario Planner. "
            "Changes apply immediately — no data reload required. "
            "Multiplier > 1.0 increases footfall; < 1.0 decreases footfall."
        )

        # Initialise session state on first visit
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
                    # Sanitise key: lowercase, spaces → underscores
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
