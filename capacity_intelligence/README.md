# Capacity Intelligence — Limited Version

A standalone Streamlit app that transforms predictive footfall data into actionable operational views for capacity planning teams.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r capacity_intelligence/requirements.txt

# 2. Run the app (from the cpg_planning_tool root directory)
streamlit run capacity_intelligence/app.py

# Or from inside the capacity_intelligence folder:
cd capacity_intelligence
pip install -r requirements.txt
streamlit run app.py
```

On first launch, go to the **⚙️ Admin** tab and click **Load Sample Data** — this activates all tabs instantly.

---

## Tabs

### 1. Short-Term View (📅)
Operational view for the next 30 or 60 days. Target audience: Regional Capacity Managers.

| Component | Description |
|---|---|
| KPI row | Peak footfall, Avg daily footfall, Buildings >90% utilization, Buildings <60% utilization |
| Building Risk Details | Expandable drilldown table — Building, City, Capacity, Peak Footfall, Avg Util %, Peak Util %, Risk label |
| Insights panel | Auto-generated bullets — buildings near capacity, Friday dip, under-utilized offices |
| Daily forecast chart | Total footfall vs capacity limit (red threshold line) |
| Day-of-week bar chart | Avg utilization % by Mon–Sun; bars colored by risk level |
| Capacity calendar | Month grid — cells colored Green (<75%), Amber (75–90%), Red (>90%) |

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
Strategic view across 6 or 12 months. Target audience: Portfolio Executives / CAO / LoB leadership.

| Component | Description |
|---|---|
| KPI row | Avg monthly footfall, Avg capacity utilization %, Surplus seats, Buildings below 50% util. |
| Long-range insights | Auto-generated bullets — breach forecasts with expected month, consolidation candidates |
| Monthly forecast chart | Avg daily footfall vs capacity limit per month |
| Building × Month heatmap | Utilization % matrix; light = low, dark = high, red = over capacity |
| City capacity table | City \| Utilization % \| Surplus — color-coded |

Filters: City, Line of Business, Building. Toggle: 6/12-month horizon.

---

### 3. Scenario Planner (🔀)
Tactical planning tool. Target audience: CPG / Workplace Strategy teams.

Two modes selectable via radio button at top:

#### Mode A — Event Impact
*"What happens to footfall when a specific event occurs?"*

- **Adjustment Scope** — apply adjustments to the whole portfolio, specific buildings, or a specific Line of Business
- Pick an **event period** (date range) — only footfall within that window is adjusted
- Select built-in adjustments (combined multiplicatively):
  - Corporate Events: Townhall (×1.20), Leadership Visit (×1.15)
  - External Disruptions: Weather Alert (×0.70), Traffic/Local Disruption (×0.80)
  - Calendar Anomalies: Mandatory Holiday (×0.10), Optional Holiday (×0.60), US Holiday (×0.75)
- Custom factor: any % adjustment (positive or negative)
- Output: Baseline vs scenario avg daily footfall (seats/day), wedge chart, per-building impact table, live impact insights panel

**KPI cards show avg weekday footfall (seats/day)** — same unit as the chart Y-axis. Total person-days impact shown as sub-caption.

#### Mode B — Policy Simulation
*"What happens if we change the RTO mandate or seat planning target?"*

- **RTO Mandate slider** (1.0–5.0 days/week, baseline 3.5) — scales footfall proportionally
- **Seat Planning Target %** (50–95%, default 80%) — seats needed = peak footfall ÷ target%
- **Horizon** toggle: 30 days / 60 days / 6 months
- Output: Current vs policy demand KPIs, monthly footfall comparison chart, per-building seat gap table

---

### 4. Admin (⚙️)
Data management tab. Two data source options:

**Use Sample Data**
- One-click load of the built-in 27-tower / 12-building synthetic dataset; activates all tabs immediately

**Upload Your Data** (two-step)
- **Step 1 — Building/Tower Master**: upload the static reference file (tower hierarchy, capacities). Only needs to be re-uploaded when buildings/towers change.
- **Step 2 — Footfall Data**: upload the daily attendance file. Re-upload any time to replace with fresh data. Auto-joins to the Master on `tower_id` and activates all tabs.
- CSV templates available for both files via download buttons

**Scenario Adjustment Configuration** (expander)
- Admin-editable table of event multipliers used in the Scenario Planner — add, edit, or delete event types without a code change

---

### 5. Help (📖)
In-app reference guide covering:
- Data model and column schema
- How the horizon date slicing works (Short-Term vs Long-Term)
- How the sample data forecast formula works (DOW multipliers, linear growth trend, noise)
- Scenario Planner calculation details (Event multipliers, RTO scaling, seat gap formula)
- Risk thresholds and utilization definitions

---

## Data Loading

### Sample Data
**~9,855 rows** — 27 towers across 12 buildings in 4 cities (Bangalore, Hyderabad, Chennai, Manila):

| City | Buildings | Towers |
|---|---|---|
| Bangalore | 3 (Prestige Tech Park, RMZ Infinity, Embassy Tech Village) | 7 |
| Hyderabad | 3 (Mindspace, DivyaSree, Raheja Mindspace) | 7 |
| Chennai | 3 (RMZ Millenia, Chennai One, TIDEL Park) | 7 |
| Manila | 3 (BGC One, Robinsons Cybergate, Eastwood City) | 6 |

Each tower has 10 floors (stored as `floor_count` column — not exposed as a filter). Mix of high-growth (Engineering, Product), stable (Sales, Finance), and declining (Operations) LoB profiles. 365 days of daily footfall — DOW patterns, per-tower linear growth trend, ±8% Gaussian noise (seed=42).

### Upload Your Own Data

The app uses **two separate files**. Go to **⚙️ Admin → Upload Your Data**.

#### File 1 — Building / Tower Master
One row per tower. Upload once; only re-upload when your building/tower list or capacities change.

| Column | Type | Example | Required |
|---|---|---|---|
| `tower_id` | string | BLR-1-TA | ✅ |
| `tower_name` | string | Tower A | ✅ |
| `building_id` | string | BLR-1 | ✅ |
| `building_name` | string | Prestige Tech Park | ✅ |
| `city` | string | Bangalore | ✅ |
| `lob` | string | Engineering | ✅ |
| `capacity` | integer | 200 | ✅ |
| `floor_count` | integer | 10 | optional |

#### File 2 — Footfall Data
One row per tower per day. Re-upload whenever you have fresh attendance data — replaces the previous load entirely.

| Column | Type | Example | Required |
|---|---|---|---|
| `date` | date (YYYY-MM-DD) | 2026-04-01 | ✅ |
| `tower_id` | string | BLR-1-TA | ✅ |
| `footfall` | integer | 168 | ✅ |

The app joins File 2 to File 1 on `tower_id`. A warning is shown if any `tower_id` in the footfall file has no matching entry in the master. **Download CSV templates** for both files are available in the Admin tab.

---

## How Calculations Work

### Horizon slicing
All views slice the loaded DataFrame to a date window starting from today. No extrapolation is performed.

| View | Horizon | Date range |
|---|---|---|
| Short-Term | 30 days | `today ≤ date < today + 30` |
| Short-Term | 60 days | `today ≤ date < today + 60` |
| Long-Term | 6 months | `today ≤ date < today + 180` |
| Long-Term | 12 months | `today ≤ date < today + 365` |

All utilization and footfall KPIs use **weekdays only (Mon–Fri)**.

### Sample data formula
```
footfall = base_demand × DOW_multiplier × trend_factor × noise

base_demand    = base_utilization × capacity
trend_factor   = 1.0 + annual_growth_rate × (day / 365)   ← linear ramp
DOW_multiplier = Mon 0.85 · Tue 1.00 · Wed 1.00 · Thu 0.95 · Fri 0.75
noise          = 1 + Normal(0, 0.08)  ← ±8%, seed=42
```

There is no statistical forecasting model (no ARIMA/Holt-Winters) in this version.

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
├── data/
│   └── ci_sample_data.py           # Sample data generator (27 towers, 12 buildings, ~9,855 rows)
├── engine/
│   ├── capacity_forecast.py        # All forecast / analysis / chart functions
│   └── scenario_report.py          # Excel report generation (4-sheet workbook)
├── tabs/
│   ├── tab_short_term.py           # Short-Term View tab
│   ├── tab_long_term.py            # Long-Term View tab
│   ├── tab_scenario_planner.py     # Scenario Planner tab (Mode A + Mode B)
│   ├── tab_admin.py                # Admin tab (data loading, scenario adjustment config)
│   └── tab_help.py                 # Help / reference tab
├── components/                     # Reusable UI components (charts, tables, metric cards)
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
- **Footfall-first** — data model is building × day; all metrics derive from daily footfall
- **Weekday-normalised averages** — all avg/peak KPIs exclude weekends for consistency
- **Admin-gated data** — data loading is in the Admin tab; analytical tabs show a guard message until data is loaded
