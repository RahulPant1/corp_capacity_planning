# CPG Seat Planning & Scenario Intelligence Platform — Claude Context

## Stack
- Python 3.11, Streamlit (multi-tab SPA), Plotly, PuLP (LP optimizer), pandas, openpyxl, ReportLab
- Entry point: `app.py`
- No database — all state in `st.session_state` via `data/session_store.py`

## Tab Layout (app.py)
| Tab | File | Purpose |
|-----|------|---------|
| 📊 Executive Dashboard | tabs/tab_executive_dashboard.py | KPIs, 1-week forecast, overflow callout, alerts, AI brief |
| 🤖 What-If Analysis | tabs/tab_optimization.py | Unit overrides, policy simulation, LP optimizer, Scenario Comparison Matrix, report download |
| 🏗️ Spatial / Floor View | tabs/tab_spatial_floor.py | Floor utilization |
| 👥 Unit Impact View | tabs/tab_unit_impact.py | Per-unit risk |
| 📈 Demand Analytics | tabs/tab_forecasting.py | Holt-Winters ETS trend forecast + MAPE badge, probabilistic demand, DOW patterns, short-term seat demand forecast (1–4 wk), peak day load balancing advisory, peak day overflow planning, demand report download (Excel + PDF) |
| 🗂️ Floor Plan Sandbox | tabs/tab_floor_sandbox.py | Interactive floor layout editing, impact simulation, re-optimize, push to scenario |
| ⚙️ Admin | tabs/tab_admin_governance.py | Data upload (with st.status progress), rule config, audit trail |

## Key Models (models/)
- `Scenario` — name, type, params (ScenarioParams), allocation_results, floor_assignments, unit_overrides
- `Floor` — floor_id (e.g. "TWR-A-F3"), building_name, tower_id, floor_number, total_seats
- `Unit` — unit_name, current_total_hc, hc_growth_pct, business_priority, night_shift_pct
- `AttendanceProfile` — unit_name, median_in_office_hc, max_in_office_hc, avg_rto_days_per_week
- `AllocationResult` — unit_name, allocated_seats, effective_demand_seats, seat_gap, fragmentation_score
- `FloorAssignment` — unit_name, tower_id, floor_number, building_id, seats_assigned, adjacency_tier

## Engine Modules (engine/)
| File | What it does |
|------|-------------|
| allocation_engine.py | Policy-based seat allocation, RTO alerts/compliance |
| optimizer.py | LP optimizer (PuLP): 3 modes — optimal_placement, rto_based, rto_whatif |
| scenario_engine.py | run_scenario(), apply_overrides(), apply_floor_modifications() |
| scenario_comparison.py | run_scenario_matrix(), rank_scenarios(), get_best_scenario(), build_explanation() |
| forecasting.py | _fit_holt_winters(), _bday_steps_ahead(), compute_unit_trend() (HW+linear fallback), compute_overall_trend(), compute_dow_patterns(), compute_week_ahead_forecast() (per-unit HW), compute_forecast_summary(), compute_percentile_demand(), compute_temporal_clustering(), compute_per_unit_forecast() (per-unit HW), compute_peak_day_per_unit(), compute_dow_conflict_analysis() |
| spatial.py | get_floor_utilization(), get_consolidation_suggestions(), assign_units_to_floors() |
| sensitivity.py | run_sensitivity_analysis() — lean/balanced/conservative buffer presets |
| report_generator.py | generate_scenario_report() → Excel bytes |
| pdf_report_generator.py | generate_pdf_report() → PDF bytes |
| demand_report_generator.py | generate_demand_report() → Excel bytes (8 sheets: demand analytics) |
| demand_pdf_report_generator.py | generate_demand_pdf_report() → PDF bytes (8 pages: demand analytics) |

## Session State (data/session_store.py)
Key getters: `get_active_scenario()`, `get_floors()`, `get_units()`, `get_attendance()`, `get_rule_config()`, `get_daily_attendance_df()`, `is_data_loaded()`
Key setters: `update_scenario()`, `set_daily_attendance()`, `add_audit_entry()`
Matrix results: `st.session_state["cmp_matrix_results"]` (list of ranked scenario dicts)

## Component Library (components/)
- `metrics_cards.py` — render_metric_row(list of dicts with label/value/delta)
- `charts.py` — capacity_vs_demand_bar, utilization_donut, rto_need_vs_allocated_bar, floor_utilization_heatmap, correlation_heatmap_chart, trend_chart, probabilistic_demand_bar
- `comparison_charts.py` — scenario_demand_capacity_bar, scenario_metrics_heatmap
- `floor_map.py` — render_floor_map_grid()
- `tables.py` — render_styled_table(), render_risk_table(), render_comparison_table()
- `sidebar.py` — render_sidebar() → sidebar_state dict

## Config (config/defaults.py) — Key Constants
- `FORECAST_EMA_SPAN`, `FORECAST_CONFIDENCE_LEVELS`, `FORECAST_BOOTSTRAP_SAMPLES`, `HW_MIN_PERIODS` (12), `HW_SEASONAL_PERIODS` (5)
- `COMPARISON_MAX_COMBINATIONS` (24), `COMPARISON_ALLOC_OPTIONS`, `COMPARISON_RTO_OPTIONS`, `COMPARISON_OBJECTIVES`
- `RISK_RED_GAP_PCT`, `RISK_AMBER_GAP_PCT`, `RISK_RED_FRAGMENTATION`, `RISK_AMBER_FRAGMENTATION`
- `FLOOR_SATURATION_THRESHOLD`, `UNIT_SHORTFALL_THRESHOLD`

## Sample Data
- `data/sample_data.py` → generates synthetic buildings/units/attendance + `generate_daily_attendance_df()` (90-day daily) + `get_sample_holiday_dates()`
- Admin "Load Sample Data" → `_load_full_sample()` with `st.status()` progress: generates all data, runs policy simulation, pre-computes cluster map, sets holiday dates — all tabs ready in one click
- `daily_df` schema: columns `date`, `unit_name`, `in_office_count`

## Typical Data Flow
1. Admin: upload data → stored via session_store setters
2. What-If Analysis: set unit overrides → "Run Policy Simulation" → run_scenario() → allocation_results populated
3. What-If Analysis: "Simulate & Optimize" → optimize_allocation() → OptimizationResult → "Accept & Apply" writes back to scenario
4. Demand Analytics: upload daily CSV → compute_week_ahead_forecast() / compute_forecast_summary() → "Apply Forecasted Growth" pushes to scenario
5. Scenario Comparison Matrix: run_scenario_matrix() → rank_scenarios() → stored as cmp_matrix_results
6. What-If Analysis: "Download Report" → generates Excel/PDF including matrix results

## Report Export (What-If Analysis → Download Report)
- Excel: generate_scenario_report(..., daily_attendance_df=..., matrix_results=...)
  Sheets: Summary, Allocation Results, Floor Assignments, Risks & Alerts, [Optimization Run], [Demand Forecast], [Scenario Comparison]
- PDF: generate_pdf_report(..., daily_attendance_df=..., matrix_results=...)
  Pages: same structure + Demand Forecast Summary + Scenario Comparison Matrix pages

## Coding Conventions
- Every tab has a top-level `render(sidebar_state)` function
- Guard all tabs: `if not is_data_loaded(): st.info(...); return`
- Plotly charts use unique `key=` strings to avoid duplicate ID errors
- Heavy imports (forecasting) done inside functions, not at module level
- All data edits log via `add_audit_entry(scenario_name, action, ...)`
- Optimizer results: `opt_result.assignments` (List[FloorAssignment]), `opt_result.unit_allocations` (dict), `opt_result.savings_summary` (dict), `opt_result.before_after` (list)
- **Performance:** tab_forecasting.py uses `@st.cache_data` module-level wrappers (e.g. `_cached_dow_patterns`, `_cached_forecast_summary`) for all heavy engine calls. Pass list args as tuples for hashability. Do not add `@st.cache_data` to engine files directly — keep engine pure Python.
- **Demand Forecast Summary:** `compute_forecast_summary()` returns `six_month_change_pct` (bounded ±100%), `trend_direction` (↑/→/↓), `suggested_growth_pct` (fraction of 6M change, used by Apply button for `hc_growth_pct`). Forecasted median = end-of-period value (fcast[-1]), floored at 0.
- **Holt-Winters model:** `compute_unit_trend()` returns `model_type` ("holt_winters" or "linear") and `mape` (float or None). All existing return fields preserved for backward compat. `_fit_holt_winters()` is lazy-imported from statsmodels inside the function. `HW_MIN_PERIODS=12`, `HW_SEASONAL_PERIODS=5` control activation threshold.
- **Demand Analytics reports:** `generate_demand_report()` and `generate_demand_pdf_report()` in engine/ accept same params: `(daily_df, unit_names, rule_config, forecast_months, summaries, stf_results, alert_days, dow_df, conflict, peak_data, breach_data, clusters, scenario, floors)`. Called from `_render_demand_download()` in tab_forecasting.py.
