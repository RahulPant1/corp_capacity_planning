# Capacity Intelligence — Limited Version

A standalone Streamlit app that transforms predictive footfall data into actionable operational views for capacity planning teams.

---

## Quick Start (development)

```bash
# From inside the capacity_intelligence folder:
pip install -r requirements.txt
streamlit run app.py
```

On first launch, go to the **⚙️ Admin** tab and click **Load Sample Data** — this activates all tabs instantly.

---

## Office Distribution (wheel-based)

The app is packaged as a Python wheel (`.whl`) for clean distribution to Windows laptops that already have Python installed. No internet connection is required on the target machine.

### Build a release (developer — run once per version)

```bat
cd capacity_intelligence
build.bat
```

This produces a `dist/` folder containing:
```
dist/
├── capacity_intelligence-0.1.0-py3-none-any.whl
├── install.bat
├── run.bat
└── README.txt
```

Copy the entire `dist/` contents to a shared network drive.

### Install on a user's laptop

> **Note:** If your IT policy requires a virtual environment, create and activate it before running `install.bat`. The scripts do not create or manage one for you.

1. Open the shared drive folder in a Command Prompt.
2. Run `install.bat` — installs the app and all dependencies from the `.whl` file (no internet needed).
3. Run `run.bat` — opens the app at `http://localhost:8501`.

### Upgrade

When a new `.whl` is published to the shared drive, users re-run `install.bat`. The `--upgrade` flag updates automatically.

### Uninstall

```bat
pip uninstall capacity-intelligence
```

---

## Tabs

### 1. Short-Term View (📅)
Operational view for the next 30 or 60 days. Target audience: Regional Capacity Managers.

| Component | Description |
|---|---|
| KPI row | Peak footfall, Avg daily footfall, Buildings >90% peak util, Buildings <60% avg util |
| Building Risk Details | Per-building risk tier, avg util %, peak util %, peak predicted seats |
| Floor Utilization | Per-floor avg util %, peak util %, risk tier |
| LOB Seat Gap | Static gap: Allocated Seats − Total Headcount per LOB (not time-series) |
| Insights panel | Auto-generated bullets — buildings near capacity, Friday dip, under-utilized offices |
| Daily forecast chart | Total predicted attendance across the horizon with a capacity reference line |
| Day-of-week bar chart | Avg utilization % by Mon–Fri — identifies low-attendance days |
| Capacity calendar | Month grid — cells colour-coded by risk tier |

Filters: City, Line of Business, Building. Toggle: 30/60-day horizon.

**Risk labels:**
| Label | Condition |
|---|---|
| 🔴 Over Capacity | Peak utilization > 90% |
| 🟡 Watch | Avg utilization > 75% |
| 🔵 Under-utilized | Avg utilization < 60% |
| 🟢 Healthy | Everything else |

---

### 2. Long-Term View (📈)
**Hidden by default.** Controlled by the `ENABLE_LONG_TERM_VIEW` flag in `config/defaults.py`.

```python
# config/defaults.py
ENABLE_LONG_TERM_VIEW = False  # set to True to show the tab
```

When `False` the tab is completely absent from the UI. Set to `True` once a 6–12 month prediction model output is available — the tab and its `tab_long_term.render()` wiring activate automatically with no other changes needed.

---

### 3. Scenario Planner (🔀)
Tactical planning tool. Target audience: CPG / Workplace Strategy teams.

Two modes selectable via radio button at top:

#### Mode A — Event Impact
*"What happens to footfall when a specific event occurs?"*

- **Adjustment Scope** — apply adjustments portfolio-wide, to specific buildings, or a specific LOB
- Pick an **event period** — preset windows (Next Week / 2 Weeks / Month) or a custom date range
- Select built-in adjustments (combined multiplicatively):
  - Corporate Events: Townhall (×1.20), Leadership Visit (×1.15)
  - External Disruptions: Weather Alert (×0.70), Traffic/Local Disruption (×0.80)
  - Calendar Anomalies: Mandatory Holiday (×0.10), Optional Holiday (×0.60), US Holiday (×0.75)
- Custom factor: any % adjustment (positive or negative)
- Output: Baseline vs scenario avg daily footfall (seats/day), wedge chart, per-building impact table, live impact insights, downloadable Excel report

**KPI cards show avg weekday footfall (seats/day).** Total person-days impact shown as sub-caption.

#### Mode B — RTO & Seat Planning
*"How many seats does each LOB need at a given RTO mandate?"*

- **RTO Mandate slider** (1–5 days/week in office, default 3 days) — converted to daily fraction internally (days ÷ 5)
- **Target Utilization slider** (50–95%, default 80%) — seats needed = expected demand ÷ target%
- Output: Portfolio seat gap KPIs, per-LOB seat gap bar chart and table, deficit/surplus summary, downloadable Excel report

```
RTO fraction                    = RTO days / 5  (e.g. 3 days/week → 60%)
Expected daily demand (per LOB) = Total Headcount × RTO fraction
Seats needed (per LOB)          = Expected demand / Target utilization %
Seat gap (per LOB)              = Allocated Seats − Seats needed
```

Uses **Total Headcount** from Dataset 3 — not actual attendance — for a consistent planning baseline.

---

### 4. Admin (⚙️)
Data management tab. Two data source options:

**Use Sample Data**
- One-click load of the built-in 12-building / 7-LOB synthetic dataset; activates all tabs immediately

**Upload Your Data** (4-dataset flow)
- Upload all four datasets below. Each has a **Download template** button and column validation on upload.
- Once all four files pass validation, datasets are **joined automatically** — no button press needed.

| Step | Dataset | Description |
|---|---|---|
| 1 | Floor Capacity | Physical seat inventory — one row per floor |
| 2 | Seat Allocation | Who sits where — one row per LOB × floor |
| 3 | Total Headcount | LOB-level total HC — one row per LOB |
| 4 | 60-Day Prediction | Model output — predicted daily attendance at floor × LOB granularity |

Individual datasets can be replaced via the **Replace** button without reloading the others.

**Scenario Adjustment Configuration** (expander)
- Admin-editable table of event multipliers used in the Scenario Planner — add, edit, or delete event types without a code change

---

### 5. Help (📖)
In-app reference guide covering:
- Getting started — how to load data (sample vs upload), step-by-step, with a dataset dependency table
- Data model and column schema for all four datasets
- Short-Term View components, metrics, and chart descriptions
- Scenario Planner calculation details (Event multipliers, RTO & seat planning formula)
- Risk thresholds and utilization definitions
- How insights are generated (rule-based, no AI)

---

## Data Loading

### Sample Data
**~3,480 rows** — 12 buildings across 4 cities (Bangalore, Hyderabad, Chennai, Manila), 7 LOBs, 2–3 floors per building with realistic multi-LOB floor sharing. 60-day predicted attendance with holiday flags.

| City | Buildings |
|---|---|
| Bangalore | Prestige Tech Park, RMZ Infinity, Embassy Tech Village |
| Hyderabad | Mindspace Hyderabad, DivyaSree, Raheja Mindspace |
| Chennai | RMZ Millenia, Chennai One, TIDEL Park |
| Manila | BGC One, Robinsons Cybergate, Eastwood City |

LOB profiles: Engineering, Product, Sales, Finance, Operations, HR, Legal — mix of high-utilization and moderate-utilization.

### Upload Your Own Data

The app uses **four separate files**. Go to **⚙️ Admin → Upload Your Data**. CSV templates are available for each.

#### Dataset 1 — Floor Capacity
One row per floor. Upload once; re-upload only when buildings or capacities change.

| Column | Type | Required |
|---|---|---|
| `City` | string | ✅ |
| `Building Name` | string | ✅ |
| `Floor` | string / integer | ✅ |
| `Total Capacity` | integer | ✅ |

#### Dataset 2 — Seat Allocation
One row per LOB × floor assignment. A floor has multiple rows when shared by several LOBs.

| Column | Type | Required |
|---|---|---|
| `LOB` | string | ✅ |
| `LOB Leader Name` | string | ✅ |
| `City` | string | ✅ |
| `Building Name` | string | ✅ |
| `Floor` | string / integer | ✅ |
| `Allocated Seats` | integer | ✅ |

#### Dataset 3 — Total Headcount
One row per LOB — total headcount across all locations, not per-floor.

| Column | Type | Required |
|---|---|---|
| `LOB` | string | ✅ |
| `Leader` | string | ✅ |
| `Headcount` | integer | ✅ |

#### Dataset 4 — 60-Day Prediction
One row per Date × City × Building × Floor × LOB. Column `Building` is accepted as an alias for `Building Name`.

| Column | Type | Required |
|---|---|---|
| `Date` | date (YYYY-MM-DD) | ✅ |
| `Day` | string (Mon, Tue…) | ✅ |
| `City` | string | ✅ |
| `Building Name` | string | ✅ |
| `Floor` | string / integer | ✅ |
| `LOB` | string | ✅ |
| `Leader` | string | ✅ |
| `Holiday Flag` | 0 / 1 | ✅ |
| `Optional Holiday Flag` | 0 / 1 | ✅ |
| `Optional Holiday Name` | string | ✅ |
| `US Holiday Flag` | 0 / 1 | ✅ |
| `Employee Count Predicted` | integer | ✅ |

**Join logic (auto-applied on load):**
```
DS4 + DS1  (on City + Building Name + Floor)
    → Utilization Pct = Employee Count Predicted / Total Capacity

DS4 + DS2  (on City + Building Name + Floor + LOB)
    → Seat Gap = Allocated Seats − Employee Count Predicted

DS2 + DS3  (on LOB)
    → HC Gap = Allocated Seats − Headcount (static snapshot)
```

---

## How Calculations Work

### Horizon slicing
All views slice the loaded DataFrame to a date window starting from today. No extrapolation is performed.

| View | Horizon | Date range |
|---|---|---|
| Short-Term | 30 days | `today ≤ date < today + 30` |
| Short-Term | 60 days | `today ≤ date < today + 60` |

All utilization and footfall KPIs use **weekdays only (Mon–Fri)**.

### Sample data formula
```
predicted = allocated_seats × lob_base_util × dow_multiplier × holiday_reduction × noise

lob_base_util   — per-LOB constant (e.g. Engineering ≈ 0.78, Operations ≈ 0.55)
dow_multiplier  — Mon 0.82 · Tue 0.95 · Wed 1.00 · Thu 0.90 · Fri 0.70
holiday_reduction — Public holiday ×0.10 · Optional holiday ×0.60 · US holiday ×0.75 · else ×1.0
noise           — 1 + Normal(0, 0.07)  ← ±7%, seed=42
```

There is no statistical forecasting model (no ARIMA / Holt-Winters) and no linear growth trend in this version.

### Scenario multipliers
Multiple event adjustments combine multiplicatively:
```
combined_mult = mult_1 × mult_2 × … × (1 + custom_pct / 100)
scenario_footfall = baseline_footfall × combined_mult
  — applied only within the event date window AND the selected scope
```

---

## Folder Structure

```
capacity_intelligence/
├── app.py                          # Streamlit entry point — page config, sidebar, tab wiring
├── cli.py                          # Wheel entry point — launches streamlit run app.py
├── pyproject.toml                  # Build config for pip-installable wheel
├── build.bat                       # Developer: builds wheel + copies deploy scripts to dist/
├── deploy/                         # Shared with users alongside the .whl
│   ├── install.bat                 # User: pip installs from local .whl
│   ├── run.bat                     # User: launches the app
│   └── README.txt                  # User-facing installation instructions
├── data/
│   └── ci_sample_data.py           # Sample data generator (12 buildings, ~3,480 rows)
├── engine/
│   ├── capacity_forecast.py        # All forecast / analysis / chart functions
│   └── scenario_report.py          # Excel report generation
├── tabs/
│   ├── tab_short_term.py           # Short-Term View tab
│   ├── tab_long_term.py            # Long-Term View tab (disabled — shows info message)
│   ├── tab_scenario_planner.py     # Scenario Planner tab (Mode A + Mode B)
│   ├── tab_admin.py                # Admin tab (data loading, scenario adjustment config)
│   └── tab_help.py                 # Help / reference tab
├── config/
│   └── defaults.py                 # Policy constants, thresholds, default scenario multipliers
└── for_future/                     # Fully built but not yet wired to UI — see for_future/README.md
    ├── engine/                     # allocation_engine, optimizer, spatial, scenario_engine, explainer
    └── models/                     # Scenario, Unit, Floor, Attendance, AuditEntry dataclasses
```

---

## Dependencies

```
streamlit
pandas
numpy
plotly
pulp
openpyxl
```

Install with: `pip install -r requirements.txt`

---

## Key Design Decisions

- **Session-state only** — no database; all state lives in `st.session_state`
- **Self-contained** — no runtime dependency on the parent `cpg_planning_tool/` codebase; can be moved to its own repository
- **Four-dataset model** — Floor Capacity + Seat Allocation + Headcount + Prediction are joined at load time; all tabs read from the single joined DataFrame
- **Weekday-normalised averages** — all avg/peak KPIs exclude weekends for consistency
- **Admin-gated data** — data loading is in the Admin tab; analytical tabs show a guard message until data is loaded
