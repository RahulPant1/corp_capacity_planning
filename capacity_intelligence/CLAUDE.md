# Capacity Intelligence — Developer Reference

This file is the primary onboarding document for developers maintaining or extending this app.
Read this before touching any code.

---

## Running the app

```bash
cd cpg_planning_tool
pip install -r capacity_intelligence/requirements.txt
streamlit run capacity_intelligence/app.py
```

First launch: go to **⚙️ Admin → Load Sample Data** to activate all tabs.

---

## Architecture in one paragraph

The app is a **pure session-state Streamlit app** — no database, no server-side persistence.
Four datasets are uploaded (or sample-generated) in the Admin tab, joined into a single
working DataFrame (`ci_daily_df`), and stored in `st.session_state`. Every analytical tab
reads exclusively from that one DataFrame. The engine layer (`engine/`) provides stateless
functions that accept DataFrames and return DataFrames or Plotly figures. Tabs call engine
functions, render results, and never write back to session state (Admin is the only exception).

---

## File map

```
app.py                      Entry point. Page config, CSS, session state init, tab wiring.
                            Feature flags are imported here from config/defaults.py.

config/
  defaults.py               All runtime constants. Two sections:
                              ACTIVE   — used by current tabs
                              FOR_FUTURE — reserved for future Seat Allocation tab

data/
  ci_sample_data.py         Generates the 4 built-in sample datasets.
                            Also defines all column name constants (COL_*) and
                            build_daily_df() which joins the 4 datasets on load.

engine/
  capacity_forecast.py      All computation and chart functions for Short-Term View
                            and Scenario Planner. Column name constants (C_*) mirror
                            those in ci_sample_data.py.
  scenario_report.py        Excel report generator. Pure pandas/openpyxl — no Streamlit.

tabs/
  tab_short_term.py         Short-Term View (30/60-day horizon)
  tab_long_term.py          Long-Term View — disabled; render() shows an info message only.
                            Controlled by ENABLE_LONG_TERM_VIEW in config/defaults.py.
  tab_scenario_planner.py   Scenario Planner (Mode A: Event Impact, Mode B: RTO & Seat Planning)
  tab_admin.py              Data loading (sample + upload), data preview, event multiplier config
  tab_help.py               In-app reference guide — no logic, pure markdown

for_future/                 Complete but unwired code for a future Seat Allocation tab.
  README.md                 Explains what is here and how to activate it.
```

---

## Session state keys

All keys are initialised with defaults in `app.py` before any tab renders.

| Key | Type | Set by | Read by |
|---|---|---|---|
| `ci_data_loaded` | bool | Admin | All analytical tabs (gate check) |
| `ci_daily_df` | DataFrame | Admin (`build_daily_df`) | All analytical tabs |
| `ci_floor_capacity_df` | DataFrame | Admin | Admin preview |
| `ci_seat_allocation_df` | DataFrame | Admin | Admin preview |
| `ci_headcount_df` | DataFrame | Admin | Admin preview |
| `ci_prediction_df` | DataFrame | Admin | Admin preview |
| `ci_buildings_meta` | list of dicts | Admin | (legacy — kept for compat) |
| `ci_data_source` | `"sample"` / `"upload"` | Admin | Sidebar, Admin banner |
| `ci_scenario_multipliers` | dict | Admin (editable table) | Scenario Planner Mode A |

**Tab guard pattern** — every analytical tab starts with:
```python
if not st.session_state.get("ci_data_loaded", False):
    st.info("No data loaded. Go to the ⚙️ Admin tab …")
    return
```
Do not skip this guard when adding new tabs.

---

## Data flow

```
Admin tab
  ├── get_floor_capacity_df()   → ci_floor_capacity_df
  ├── get_seat_allocation_df()  → ci_seat_allocation_df
  ├── get_headcount_df()        → ci_headcount_df
  ├── get_prediction_df()       → ci_prediction_df
  └── build_daily_df(DS1, DS2, DS3, DS4)
        ├── joins on (City, Building Name, Floor) for capacity + allocation
        ├── joins on LOB for headcount
        └── adds derived columns:
              Utilization Pct  = Predicted / Total Capacity  (clipped at 1.30, stored as fraction)
              Seat Gap         = Allocated Seats − Predicted
              HC Gap           = Allocated Seats − Headcount
        → ci_daily_df   (read by every tab)
```

---

## Known gotchas

**Capacity deduplication** — `Total Capacity` is the same value repeated for every LOB on a
floor. When aggregating capacity to building or portfolio level, always de-duplicate on
`(City, Building Name, Floor)` first, otherwise capacity is double/triple-counted.
The engine helper `_building_daily()` handles this correctly — use it instead of raw groupby.

**Imports inside render()** — every tab does its imports inside the `render()` function, not
at module top. This avoids circular import issues when Streamlit reruns the module and keeps
cold-start time low. Do not move them to module level.

**Plotly key= strings** — every `st.plotly_chart()` call requires a unique `key=` string.
Without it Streamlit reuses the widget and charts may not update. Use a short tab-prefix
convention, e.g. `key="st_forecast_line"` for Short-Term, `key="sp_wedge"` for Scenario Planner.

**Utilization Pct is a fraction, not a percentage** — `ci_daily_df["Utilization Pct"]` stores
values between 0 and 1.30. Multiply by 100 before displaying. The engine functions that
return display tables (`compute_floor_utilization`, etc.) already do this and label the
columns `Avg Util %` / `Peak Util %`.

**RTO fraction** — in Mode B, `rto_days` (1–5) is converted to `rto_fraction = rto_days / 5`
before being passed to engine functions. Engine functions always receive the fraction (0–1),
never the raw day count.

---

## Adding a new tab

1. Create `tabs/tab_<name>.py` with a single `render()` function.
2. Start render() with the tab guard (see pattern above).
3. Do all imports inside render().
4. In `app.py`:
   - Add the emoji label to `_tab_labels`
   - Import the module
   - Add a `with _t_<name>: tab_<name>.render()` block
5. If the tab should be feature-flagged, add a constant to `config/defaults.py` (follow the
   `ENABLE_LONG_TERM_VIEW` pattern) and gate both the label and the render call on it.

---

## Adding a new engine function

1. Add the function to the relevant file in `engine/` — use `capacity_forecast.py` for
   anything that reads from `ci_daily_df`, or create a new `engine/<name>.py` for a
   distinct concern (see `scenario_report.py` as an example of a self-contained generator).
2. Import inside the tab's `render()` function, not at module top.
3. Functions should accept DataFrames and return DataFrames or Plotly figures.
   They must not read from or write to `st.session_state`.

---

## Adding a new event type to the Scenario Planner

Event multipliers live in `config/defaults.py → DEFAULT_SCENARIO_MULTIPLIERS`.
Admins can also add/edit/delete event types at runtime via **Admin → Scenario Adjustment
Configuration** without a code change. The runtime values are stored in
`st.session_state["ci_scenario_multipliers"]` and override the defaults for that session.

---

## Feature flags

| Flag | File | Default | Effect when True |
|---|---|---|---|
| `ENABLE_LONG_TERM_VIEW` | `config/defaults.py` | `False` | Adds Long-Term View tab to the UI |

---

## Column name constants — two sources of truth

Column names are defined in **two places** that must stay in sync:

| File | Prefix | Used by |
|---|---|---|
| `data/ci_sample_data.py` | `COL_*` | `build_daily_df()`, Admin tab |
| `engine/capacity_forecast.py` | `C_*` | All engine functions, analytical tabs |

Both sets refer to the same physical column names (e.g. `COL_BUILDING = C_BUILDING = "Building Name"`).
If you rename a column, update both files.

---

## Dependency map (import graph)

```
app.py
  ├── config.defaults          (ENABLE_LONG_TERM_VIEW, DEFAULT_SCENARIO_MULTIPLIERS)
  └── tabs/
        ├── tab_short_term     → engine.capacity_forecast
        ├── tab_long_term      (no engine imports — disabled)
        ├── tab_scenario_planner → engine.capacity_forecast
        │                        → engine.scenario_report
        │                        → config.defaults
        ├── tab_admin          → data.ci_sample_data
        │                        → config.defaults
        └── tab_help           (no engine imports — pure markdown)

data.ci_sample_data            (standalone — no engine imports)
engine.capacity_forecast       (standalone — no tab/data imports)
engine.scenario_report         (standalone — no tab/data imports)
```

No circular dependencies. Each layer only imports from layers below it.
