# Capacity Intelligence — Limited Version

A standalone Streamlit app that transforms predictive footfall data into three actionable operational views for capacity planning teams.

---

## Quick Start

```bash
# From the cpg_planning_tool root directory:
streamlit run capacity_intelligence/app.py

# Or from inside the capacity_intelligence folder:
cd capacity_intelligence
streamlit run app.py
```

The app auto-loads sample data on startup — no configuration needed.

---

## Views

### 1. Short-Term View (📅)
Operational view for the next 30 or 60 days. Target audience: Regional Capacity Managers.

| Component | Description |
|---|---|
| KPI row | Peak footfall, Avg daily footfall, Buildings >90% utilization, Buildings <60% utilization |
| Insights panel | Auto-generated bullets — buildings near capacity, Friday dip, under-utilized offices |
| Daily forecast chart | Total footfall vs capacity limit (red threshold line) |
| Day-of-week bar chart | Avg utilization % by Mon–Sun; bars colored by risk level |
| Capacity calendar | Month grid — cells colored Green (<75%), Amber (75–90%), Red (>90%) |

Filters: City, Line of Business, Building. Toggle: 30/60-day horizon, Peak/Average metric.

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

Filters: Country, City, Line of Business, Building. Toggle: 6/12-month horizon.

---

### 3. Scenario Planner (🔀)
Tactical planning tool. Target audience: CPG / Workplace Strategy teams.

Two modes selectable via radio button at top:

#### Mode A — Event Impact
*"What happens to footfall when a specific event occurs?"*

- Pick an **event period** (date range) — only footfall within that window is adjusted
- Select built-in adjustments:
  - Corporate Events: Townhall (+20%), Leadership Visit (+15%)
  - External Disruptions: Weather Alert (−30%), Traffic/Local Disruption (−20%)
  - Calendar Anomalies: Mandatory Holiday (−90%), Optional Holiday (−40%), US Holiday (−25%)
- Custom factor: any % adjustment (positive or negative)
- Output: Baseline vs scenario KPIs, wedge chart (divergence visualised), per-building impact table

#### Mode B — Policy Simulation
*"What happens if we change the RTO mandate or seat planning target?"*

- **RTO Mandate slider** (1.0–5.0 days/week, baseline 3.5) — scales footfall proportionally across the full horizon
- **Seat Planning Target %** (50–95%, default 80%) — determines seats needed = peak footfall ÷ target%
- **Horizon** toggle: 30 days / 60 days / 6 months
- Output: Current vs policy demand KPIs, monthly footfall comparison chart, per-building seat gap table (Surplus/Deficit)

---

## Data Loading

The sidebar (left panel) offers two options:

### Sample Data (default)
7 synthetic buildings across Bangalore, Hyderabad, Chennai, and Manila with realistic utilization profiles:
- Mix of high-growth (Engineering, Product), stable (Sales, Finance), and declining (Operations) units
- Intentionally includes buildings near capacity and under-utilized buildings for demo value
- 365 days of daily footfall with DOW patterns, linear growth trend, and Gaussian noise

### Upload Your Own CSV
Click "Upload CSV" in the sidebar. The file must contain these columns:

| Column | Type | Example |
|---|---|---|
| `date` | date (YYYY-MM-DD) | 2026-04-01 |
| `building_id` | string | BLR-ENG |
| `building_name` | string | Bangalore Engineering Hub |
| `city` | string | Bangalore |
| `country` | string | India |
| `lob` | string | Engineering |
| `footfall` | integer | 412 |
| `capacity` | integer | 500 |

A **Download CSV template** button is available in the sidebar to get the correct column headers.

Each row = one building on one day. For multi-building portfolios, include one row per building per day.

---

## Folder Structure

```
capacity_intelligence/
├── app.py                      # Streamlit entry point
├── data/
│   └── ci_sample_data.py       # Sample data generator (7 buildings, 365-day forecast)
├── engine/
│   ├── capacity_forecast.py    # All forecast/analysis/chart functions
│   ├── allocation_engine.py    # Seat allocation engine (from CPG planning tool)
│   ├── optimizer.py            # LP optimizer (from CPG planning tool)
│   ├── scenario_engine.py      # Scenario simulation engine (from CPG planning tool)
│   └── spatial.py              # Floor assignment engine (from CPG planning tool)
├── models/                     # Data models (Scenario, Unit, Floor, Attendance, etc.)
├── components/                 # Reusable UI components (charts, tables, metric cards)
└── config/
    └── defaults.py             # Policy constants and thresholds
```

The `engine/`, `models/`, `components/`, and `config/` subfolders were copied from the parent CPG planning tool and are now independent — changes here do not affect the parent app.

---

## Dependencies

Uses the same Python environment as the parent CPG planning tool:

```
streamlit
pandas
numpy
plotly
pulp
```

No additional packages required.

---

## Key Design Decisions

- **Session-state only** — no database; all state lives in `st.session_state`
- **Self-contained** — this folder has no runtime dependency on the parent `cpg_planning_tool/` codebase; it can be moved to its own repository
- **Footfall-first** — the data model is building × day (not unit × month like the parent tool); all metrics derive from this daily footfall series
- **Synthetic forecast** — sample data is generated deterministically (fixed seed) using DOW multipliers, linear growth trend, and Gaussian noise; re-running produces the same data
