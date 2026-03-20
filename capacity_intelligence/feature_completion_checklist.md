# Capacity Intelligence — Feature Completion Checklist

> Audit date: 2026-03-20 · Last updated: 2026-03-20 (second review, post-cleanup)
> Version: Limited Version (Streamlit)
> Scope: All files in `capacity_intelligence/`

---

## Legend
- ✅ Complete and wired to UI
- 🔧 Built, parked in `for_future/` — not yet wired to any tab
- ⚠️ Minor note
- ❌ Not yet built

---

## 1. Application Shell

| Feature | Status | Notes |
|---|---|---|
| Streamlit page config (title, icon, layout) | ✅ | Configured in `app.py` |
| Global CSS / style overrides | ✅ | `.insight-box`, `.section-header`, metric font-size |
| Session-state initialisation | ✅ | `ci_data_loaded`, `ci_daily_df`, `ci_buildings_meta`, `ci_data_source` |
| 5-tab navigation bar | ✅ | Short-Term, Long-Term, Scenario Planner, Admin, Help |
| Sidebar | ✅ | Shows live data status (source, row count, date range) or "No data loaded" prompt |

---

## 2. Admin Tab (⚙️)

| Feature | Status | Notes |
|---|---|---|
| Data source radio toggle (Sample / Upload) | ✅ | |
| Load sample data button | ✅ | Generates 27-tower, 9,855-row dataset |
| Data active status banner | ✅ | Shows source, building count, tower count, days |
| Clear data button | ✅ | Resets all `ci_*` session state keys |
| CSV upload with column validation | ✅ | Validates all 7 required columns, surfaces missing ones |
| Download CSV template button | ✅ | Pre-columns template with `REQUIRED_COLS` |
| Optional column support (tower_id, tower_name, floor_count) | ✅ | Graceful degradation when absent |
| Data preview — row count, date range, buildings/towers | ✅ | Shows metrics + first 20 rows |
| Per-building/tower summary table with Avg Util % | ✅ | Dynamic: tower view vs building view |
| Scenario Adjustment Configuration expander | ✅ | Editable multiplier table with Save + Reset |
| Runtime multiplier sync to Scenario Planner | ✅ | Read via `st.session_state["ci_scenario_multipliers"]` |

---

## 3. Short-Term View Tab (📅)

| Feature | Status | Notes |
|---|---|---|
| Data-loaded guard (info banner if no data) | ✅ | |
| City multiselect filter | ✅ | |
| Building multiselect filter (cascades from city) | ✅ | |
| Line of Business multiselect filter | ✅ | |
| Horizon toggle: 30 / 60 days | ✅ | |
| **KPI Cards** | | |
| — Peak Footfall + % of capacity delta | ✅ | |
| — Avg Daily Footfall + % of capacity delta | ✅ | |
| — Buildings >90% utilization (with risk indicator) | ✅ | |
| — Buildings <60% utilization (with indicator) | ✅ | |
| **Building Risk Details expander** | | |
| — Aggregated to building-day level (tower-aware) | ✅ | |
| — Sortable: Building, City, LoB, Capacity, Peak Footfall, Avg/Peak Util % | ✅ | |
| — Risk labels (🔴🟡🔵🟢) with color styling | ✅ | |
| **Insights panel** (rule-based, up to 5 bullets) | ✅ | Over-capacity, Fri vs Wed dip, under-utilized |
| **Daily forecast line chart** (footfall vs capacity threshold) | ✅ | |
| **Day-of-week bar chart** (avg util %, risk-colored bars) | ✅ | 90% threshold line |
| **Capacity calendar** (month grid, color-coded cells) | ✅ | Green/Amber/Red by utilization |

---

## 4. Long-Term View Tab (📈)

| Feature | Status | Notes |
|---|---|---|
| Data-loaded guard | ✅ | |
| City multiselect filter | ✅ | |
| Building multiselect filter (cascades from city) | ✅ | |
| Line of Business multiselect filter | ✅ | |
| Country filter | — | Intentionally removed; `filter_df()` signature updated to match |
| Horizon toggle: 6 / 12 months | ✅ | |
| **KPI Cards** | | |
| — Avg Monthly Footfall | ✅ | |
| — Avg Capacity Utilization % (with high-risk delta) | ✅ | |
| — Surplus Seats (with over-capacity risk indicator) | ✅ | |
| — Buildings Below 50% Utilization | ✅ | |
| **Long-Range Insights panel** (up to 5 bullets) | ✅ | Breach forecasts + consolidation candidates |
| **Monthly forecast line chart** (avg daily footfall vs capacity) | ✅ | Uses `plot_monthly_forecast_simple()` |
| `plot_monthly_forecast()` dead code | ✅ | Removed — `plot_monthly_forecast_simple()` is the sole active version |
| **Building × Month utilization heatmap** | ✅ | Filtered to selected horizon; color scale light→dark→red |
| **City capacity table** (Util %, Surplus, color-coded) | ✅ | |

---

## 5. Scenario Planner Tab (🔀)

### Mode A — Event Impact

| Feature | Status | Notes |
|---|---|---|
| Mode radio toggle (Event Impact / Policy Simulation) | ✅ | |
| LoB and Building filters | ✅ | |
| Adjustment Scope radio (Portfolio / Specific Buildings / Specific LoB) | ✅ | |
| Event date range picker | ✅ | Default +7 to +21 days; bounded to today → +365 |
| Built-in event checkboxes (dynamic from Admin config) | ✅ | Grouped: Corporate, Disruptions, Calendar, Other |
| Custom % adjustment input | ✅ | |
| Multiplicative combination of multipliers | ✅ | |
| **KPI Cards**: Baseline Avg Daily / Scenario Avg Daily / Event Window | ✅ | |
| Sub-caption: total person-days impact | ✅ | |
| **Wedge chart** (baseline vs scenario with shaded area + date markers) | ✅ | |
| **Per-building impact table** (Baseline / Scenario / Difference, color-coded) | ✅ | |
| **Live Impact Insights expander** (5 bullets) | ✅ | Total delta, risk days, avg daily change, top building, scope coverage |
| **Excel Impact Report download** (.xlsx, 4 sheets) | ✅ | Summary, Building Impact, Daily Data, Insights |

### Mode B — Policy Simulation

| Feature | Status | Notes |
|---|---|---|
| LoB and Building filters | ✅ | |
| RTO Mandate slider (1.0–5.0 days/week) | ✅ | Baseline 3.5 days/week |
| RTO caption showing % change from baseline | ✅ | |
| Seat Planning Target % slider (50–95%) | ✅ | |
| Horizon toggle: 30 days / 60 days / 6 months | ✅ | |
| **KPI Cards**: Current Demand / Policy Demand / Portfolio Seat Gap / Total Capacity | ✅ | |
| **RTO comparison line chart** (current vs new policy, monthly avg) | ✅ | |
| **Seat Gap by Building table** (Surplus / Deficit, color-coded) | ✅ | |
| **Excel Impact Report download** (.xlsx) | ✅ | Includes mode params sheet |

---

## 6. Help Tab (📖)

| Feature | Status | Notes |
|---|---|---|
| Section 1: Data Model (required + optional columns) | ✅ | |
| Section 2: How the Horizon Works (date slicing table) | ✅ | |
| Section 3: How Forecasting Works (formula breakdown) | ✅ | |
| Section 4: Scenario Planner Calculations (Mode A + B, Excel report) | ✅ | |
| Section 5: Risk Thresholds & Utilization | ✅ | |
| Section 6: How Insights Are Generated (per-tab rule tables) | ✅ | |

---

## 7. Engine — Capacity Forecast (`capacity_forecast.py`)

| Function | UI-Wired | Notes |
|---|---|---|
| `filter_df()` | ✅ | Used by all tabs |
| `get_horizon_df()` | ✅ | |
| `compute_portfolio_kpis()` | ✅ | Short-Term KPIs |
| `compute_dow_averages()` | ✅ | |
| `compute_monthly_utilization()` | ✅ | Long-Term heatmap |
| `compute_long_term_kpis()` | ✅ | |
| `compute_city_capacity_metrics()` | ✅ | |
| `generate_insights_short_term()` | ✅ | |
| `generate_insights_long_term()` | ✅ | |
| `apply_scenario_adjustments()` | ✅ | |
| `compute_live_insights()` | ✅ | |
| `compute_scenario_kpis()` | ✅ | |
| `compute_building_impact_table()` | ✅ | |
| `plot_daily_forecast()` | ✅ | |
| `plot_dow_bar()` | ✅ | |
| `plot_capacity_calendar()` | ✅ | |
| `plot_monthly_forecast_simple()` | ✅ | |
| `plot_building_heatmap()` | ✅ | |
| `plot_scenario_wedge()` | ✅ | |
| `simulate_rto_policy()` | ✅ | |
| `compute_seat_gap_by_building()` | ✅ | |
| `compute_policy_kpis()` | ✅ | |
| `plot_rto_comparison()` | ✅ | |
| `plot_monthly_forecast()` | ✅ | Removed |

---

## 8. Engine — Allocation Engine (`for_future/engine/allocation_engine.py`)

> Moved to `for_future/` — backend-complete but not connected to any Streamlit tab. See `for_future/README.md`.

| Function | UI-Wired | Notes |
|---|---|---|
| `compute_recommended_allocation()` | 🔧 | Attendance-based advanced allocation formula |
| `compute_simple_allocation()` | 🔧 | Flat % allocation with growth projection |
| `compute_all_allocations()` | 🔧 | Batch run for all units |
| `distribute_seats()` | 🔧 | Scarcity-aware seat distribution with priority ordering |
| `run_allocation()` | 🔧 | Full pipeline: compute + distribute |
| `compute_rto_alerts()` | 🔧 | Per-unit RTO utilization alerts |
| `compute_rto_compliance()` | 🔧 | Units below global RTO target |

---

## 9. Engine — LP Optimizer (`for_future/engine/optimizer.py`)

> Moved to `for_future/` — fully built using PuLP CBC solver. Not connected to any UI tab.

| Feature | UI-Wired | Notes |
|---|---|---|
| `optimize_allocation()` — `optimal_placement` objective | 🔧 | Minimize floors + building spread |
| `optimize_allocation()` — `rto_based` objective | 🔧 | Allocate by actual attendance patterns |
| `optimize_allocation()` — `rto_whatif` objective | 🔧 | Simulate different RTO mandate |
| Max-floors-per-unit constraint | 🔧 | |
| Tower-pinning constraint | 🔧 | |
| Minimum seat guarantee constraint (with graceful relaxation) | 🔧 | |
| Building-spread penalty | 🔧 | |
| Adjacent floor reward | 🔧 | |
| Before/After comparison output | 🔧 | |
| Consolidation suggestions output | 🔧 | |
| RTO savings summary output | 🔧 | |

---

## 10. Engine — Spatial (`for_future/engine/spatial.py`)

> Moved to `for_future/` — greedy floor-assignment engine with adjacency scoring. Not connected to any UI tab.

| Function | UI-Wired | Notes |
|---|---|---|
| `compute_adjacency_tier()` | 🔧 | |
| `score_floor_for_unit()` | 🔧 | |
| `assign_units_to_floors()` | 🔧 | Used by `scenario_engine.py` only |
| `get_floor_utilization()` | 🔧 | |
| `get_consolidation_suggestions()` | 🔧 | |

---

## 11. Engine — Scenario Engine (`for_future/engine/scenario_engine.py`)

> Moved to `for_future/` — manages full scenario lifecycle with unit/floor overrides. Not connected to any UI tab.
> The Scenario Planner tab uses the simpler `capacity_forecast.py` approach instead.

| Function | UI-Wired | Notes |
|---|---|---|
| `apply_overrides()` | 🔧 | Per-unit HC, RTO, and global RTO mandate |
| `apply_floor_modifications()` | 🔧 | Floor exclusion + capacity reduction % |
| `run_scenario()` | 🔧 | Full pipeline: overrides → allocation → floor assignment |
| `compare_scenarios()` | 🔧 | Side-by-side diff of two scenario results |

---

## 12. Engine — Scenario Report (`scenario_report.py`)

| Feature | Status | Notes |
|---|---|---|
| Summary sheet (KPIs + mode params) | ✅ | |
| Building Impact sheet | ✅ | |
| Daily Data sheet (baseline vs scenario + delta + delta%) | ✅ | |
| Insights sheet (emoji/markdown stripped for Excel) | ✅ | |
| Auto-fit column widths | ✅ | |

---

## 13. Models (`for_future/models/`)

> All model files moved to `for_future/models/` — not referenced by any active tab.

| Model | Status | Notes |
|---|---|---|
| `Scenario` / `ScenarioOverride` / `ScenarioParams` | 🔧 | Used only by for_future/engine/scenario_engine.py |
| `AllocationRecommendation` / `FloorAssignment` | 🔧 | Used only by for_future allocation/spatial/optimizer engines |
| `Unit` | 🔧 | Not surfaced in any tab |
| `AttendanceProfile` | 🔧 | Not surfaced in any tab |
| `Building` / `Floor` | 🔧 | Not surfaced in any tab |
| `AuditEntry` | 🔧 | Defined but not used anywhere in this codebase |

---

## 14. Configuration (`config/defaults.py`)

| Constant | UI-Wired | Notes |
|---|---|---|
| `DEFAULT_SCENARIO_MULTIPLIERS` | ✅ | Admin tab editable; Scenario Planner reads it |
| `ALLOCATION_MODE` | 🔧 | Defined (`"simple"`); no UI toggle to switch modes |
| `DEFAULT_GLOBAL_ALLOC_PCT` | 🔧 | Used by allocation engine, not accessible from UI |
| `MIN_ALLOC_PCT` / `MAX_ALLOC_PCT` | 🔧 | Policy bounds for allocation engine |
| `PLANNING_BUFFER_PRESETS` (lean/balanced/conservative) | 🔧 | Defined; no UI to select a preset |
| `PEAK_BUFFER_MULTIPLIER` | 🔧 | |
| `PRIORITY_ORDER` | 🔧 | Scarcity allocation priority |
| `ADJACENCY_BONUS_*` constants | 🔧 | Used by spatial engine only |
| `FLOOR_SATURATION_THRESHOLD` | 🔧 | Defined; no UI alert uses it |
| `RISK_RED_GAP_PCT` / `RISK_AMBER_*` thresholds | 🔧 | Defined; no UI component reads them |

---

## 15. Data / Sample Data (`data/ci_sample_data.py`)

| Feature | Status | Notes |
|---|---|---|
| 27 towers across 12 buildings, 4 cities | ✅ | Bangalore (9 towers), Hyderabad (6), Chennai (6), Manila (6) |
| 365-day deterministic footfall generation (seed=42) | ✅ | |
| DOW multipliers, linear growth trend, Gaussian noise | ✅ | |
| Mix of high-growth, stable, and declining units | ✅ | |
| `REQUIRED_COLS` / `OPTIONAL_COLS` constants for upload validation | ✅ | |
| `get_buildings_meta()` returning building-level aggregates | ✅ | |

---

## 16. Documentation

| Item | Status | Notes |
|---|---|---|
| `README.md` — Quick Start, Tabs overview, Data Loading, Calculations | ✅ | |
| README sample data description | ✅ | Updated: 4 cities, 12 buildings, 27 towers, ~9,855 rows |
| README folder structure | ✅ | Updated: includes `tabs/`, `for_future/`, `scenario_report.py` |
| In-app Help tab | ✅ | Comprehensive 6-section reference |
| `requirements.txt` | ✅ | `openpyxl>=3.1.0` added |

---

## Summary

| Category | Count |
|---|---|
| ✅ Complete and UI-wired | ~80 features |
| 🔧 Built, parked in `for_future/` | ~30 functions (5 engine files + 6 model files) |
| ⚠️ Minor open item | 1 |
| ❌ Not built | 0 |

### All Original Gaps — Resolved ✅

| # | Gap | Resolution |
|---|---|---|
| 1 | `openpyxl` missing from `requirements.txt` | Added: `openpyxl>=3.1.0` |
| 2 | Allocation engine, optimizer, spatial, scenario engine unreachable | Moved to `for_future/` with its own README and activation guide |
| 3 | Dead `plot_monthly_forecast()` function | Removed; `plot_monthly_forecast_simple()` is now the only version |
| 4 | Country filter parameter with no UI control | Removed from `filter_df()` signature — intentionally dropped |
| 5 | README sample data count stale ("7 buildings") | Updated to 27 towers / 12 buildings / 4 cities |
| 6 | Sidebar showed only a run-command | Now shows live data status: source, row count, date range |
| 7 | `AuditLog` model in `models/` not used anywhere | Moved to `for_future/models/audit.py` with description in its README |
| 8 | `PLANNING_BUFFER_PRESETS` and related constants with no UI | Documented as `for_future` in `config/defaults.py` context |

### One Remaining Item

**`config/defaults.py` contains constants that only serve `for_future/` engines** (e.g. `RISK_RED_GAP_PCT`, `FLOOR_SATURATION_THRESHOLD`, `PLANNING_BUFFER_PRESETS`). These are harmless and intentional, but could benefit from a brief inline comment tagging them as "for Seat Allocation tab" to prevent confusion for future contributors. Non-blocking.
