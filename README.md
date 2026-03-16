# CPG Seat Planning & Scenario Intelligence Platform

A data-driven seat planning and LP-optimization tool for office portfolio management. Combines flat allocation policy with attendance data (Median HC, Peak HC, RTO patterns) and PuLP-based floor assignment optimization to produce actionable seat plans across buildings, towers, and floors.

## Setup

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
cd cpg_planning_tool
pip install -r requirements.txt
```

### Launch

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Quick Start

1. Open the app → **Admin** tab → click **"Load Sample Data"**
   - Loads 2 buildings, 20 floors, 8 business units, 90 days of attendance history
   - Runs the baseline policy simulation and pre-warms all tabs in one click
2. Go to **What-If Analysis** → adjust sliders → click **"Run & Optimize"**
3. Explore results across all tabs (Dashboard, Floor View, Unit Impact are all populated)
4. Click **"Accept & Apply"** in What-If to commit the optimized floor assignments to the active scenario

---

## Uploading Your Data

Upload via the **Admin** tab. Two options:

### Option A: Single Excel File (Recommended)

One `.xlsx` file with 3 sheets:

| Sheet | Accepted Names |
|-------|---------------|
| Buildings | `Buildings`, `Building Master`, `Floors`, `Floor Master` |
| Units | `Units`, `Headcount`, `Unit HC`, `Unit Headcount` |
| Attendance | `Attendance`, `RTO`, `RTO Behavior`, `Attendance & RTO` |

### Option B: Three Separate Files

Three individual files (CSV or single-sheet Excel), one per dataset.

---

## Data Schemas

### File 1: Building & Floor Master

One row per floor.

| Column | Description | Example |
|--------|-------------|---------|
| `Building ID` | Unique building identifier | B1 |
| `Building Name` | Human-readable building name | HQ Campus |
| `Tower ID` | Unique tower identifier | B1-T1 |
| `Floor Number` | Floor number within the tower | 3 |
| `Total Seats` | Available seats on this floor | 120 |

### File 2: Unit Headcount & Forecast

One row per business unit.

| Column | Description | Example |
|--------|-------------|---------|
| `Unit Name` | Business unit name | Engineering |
| `Current Total Headcount` | Current HC | 400 |
| `HC Growth Forecast (%)` | Expected net growth % over planning horizon | 15 |
| `Business Priority` | *(Optional)* High / Medium / Low — used for scarcity prioritization | High |
| `Night Shift %` | *(Optional)* % of HC on night shift; enables hot-seating. Default: 0 | 10 |

### File 3: Attendance & RTO Behavior

One row per business unit. Unit names must match File 2.

| Column | Description | Example |
|--------|-------------|---------|
| `Unit Name` | Must match the headcount file | Engineering |
| `Monthly Median In-Office Strength` | Median employees in-office per month | 250 |
| `Monthly Max In-Office Strength` | Peak employees in-office per month | 320 |
| `Avg RTO Days/Week` | Average RTO days per week (0–5) | 3.5 |

---

## How Allocation Works

### Simple Mode (default)

Each unit receives a flat `global_alloc_pct` of their headcount as seats, adjusted for growth.

| Step | Formula | Example |
|------|---------|---------|
| 1. Base % | Global default (e.g., 80%) or per-unit override | 80% |
| 2. Growth adjustment | Base % × (1 + Growth% × months/12) | 80% × 1.075 = 86% |
| 3. Policy clamp | Clamped to [min, max] bounds (default 20%–150%) | 86% |
| 4. Effective demand | Clamped % × Current HC | 86% × 400 = 344 seats |

### Night Shift & Hot-Seating

Units with `Night Shift %` > 0 share desks between day/night workers:

| Step | Formula | Example (400 HC, 80% alloc, 10% night) |
|------|---------|--------------------------------------|
| Effective demand | Alloc% × HC | 320 seats |
| Day demand | Effective × (1 − Night%) | 320 × 0.90 = 288 |
| Night demand | Effective × Night% | 320 × 0.10 = 32 |
| Physical demand | max(Day, Night) | 288 seats |
| Hot-seat savings | Effective − Physical | **32 seats saved** |

### Attendance-Based Validation

After allocation, every unit is validated against actual RTO behavior:

```
RTO Need = (Median HC + Peak Buffer) × (RTO Days / 5)
```

Units where allocated seats exceed RTO Need are flagged as over-provisioned; units below RTO Need are flagged as under-allocated.

---

## Application Tabs

### Tab 1 — 📊 Executive Dashboard

Leadership summary, always read-only:

- **KPI cards** — Effective Supply, Total Demand, Seat Gap, Units with Shortfall
- **Active Scenario Constraints** — info callout showing all applied constraints (excluded floors, capacity reduction, RTO mandate, tower restrictions, unit overrides, optimizer mode)
- **Key Insights** — up to 5 rule-based cards (🔴 risk / 💡 opportunity / 📊 neutral)
- **Capacity vs Demand chart** by tower + utilization donut
- **1-Week Seat Demand Forecast** — bar chart of next 7 business days; HIGH/MEDIUM/LOW risk coloring
- **Peak Day Overflow Callout** — fires when any forecast day exceeds 90% capacity
- **Planning Alerts** — collapsible expanders for Capacity, RTO, and Other alerts
- **Executive Report Download** — consolidated Excel workbook (scenario + demand + floor intelligence)
- Stale-data warning when base data has changed since the last simulation

### Tab 2 — 🤖 What-If Analysis

Central planning and optimization hub:

**Optimization modes:**

| Mode | Demand basis | Alloc % used? |
|------|-------------|---------------|
| **Optimal Placement** | HC × Alloc % | ✅ Yes |
| **RTO-Based** | Actual attendance data | ❌ No |
| **What-If RTO** | Attendance × target RTO | ❌ No |

**Planning controls:**
- Global Alloc % (50–150%), Global RTO Mandate / Target RTO (0.5–5 days/wk), Capacity Reduction % (0–15%)
- Max Floors Per Unit, Minimum Seat Guarantee %
- **Tower Restrictions** *(expander)* — pin units to specific towers
- **Unit-Level Overrides** *(expander)* — per-unit HC growth % and alloc % override

**Single "Run & Optimize" button** — applies all overrides, reruns the policy allocation, then LP-optimizes floor assignments.

**Results panel:**
- Planning Impact vs baseline (demand delta, capacity delta, headroom)
- Before/After table (per-unit seats, floor count, buildings used)
- Savings Summary for RTO-based modes (seats saved, floors freed)
- Consolidation suggestions
- Optimization history (last 3 runs)
- **Accept & Apply** — commits floor assignments to the active scenario

**Scenario Comparison Matrix** *(expander)* — runs up to 12 parameter combinations (Alloc %, RTO, Cap Reduction, Mode) through the full simulation + LP pipeline and ranks by composite score (headroom 35%, gap 35%, fragmentation 15%, consolidation 15%). Ranked table + demand/capacity chart + metrics heatmap.

**Report Download** — Excel workbook (Scenario Summary, Allocation Results, Floor Assignments, Risks & Alerts, Optimization Run, Demand Forecast, Scenario Comparison).

### Tab 3 — 🏗️ Spatial / Floor View

Physical seat utilization across towers and floors. Two view modes:

- **Charts view** — floor utilization bar chart + unit-by-floor heatmap
- **Floor Map view** — color-coded treemap blocks per floor showing each unit's allocation proportionally

Both views include a floor detail table, building spread analysis, and consolidation suggestions.

### Tab 4 — 👥 Unit Impact View

Per-unit risk table with 🔴/🟡/🟢 summary cards. Filter by priority, risk level, or unit name. Columns: current/projected HC, recommended alloc %, effective demand, allocated seats, gap, fragmentation score, risk level, RTO status.

### Tab 5 — 📈 Demand Analytics

Driven by daily attendance data (CSV: Date, Unit Name, In-Office Count):

**Attendance Trends & Forecast:**
- Holt-Winters ETS (level + trend + Mon–Fri seasonality) with 95% confidence bands; falls back to linear regression for sparse data
- 5 metric cards: Current Median, Trend Slope, Residual Std, 6M Forecast, Model + MAPE
- **Forecast Summary table** — per-unit 6M change in seats and %, trend direction (↑/→/↓)
- **"Apply 6-Month Growth Estimate"** — pushes data-driven growth % into scenario overrides

**Short-Term Seat Demand Forecast:**
- 5/10/15/21-day horizons; holiday-aware; capacity risk threshold at 90%
- Color-coded bar chart (green/amber/red) + per-unit breakdown toggle

**Peak Day Overflow Planning** *(auto-shown when alert days exist)* — risk days, overflow floors, at-risk units.

**Probabilistic Demand:** 90th/95th/99th percentile demand via Bootstrap Monte Carlo.

**Day-of-Week Patterns:** Heatmap (units × Mon–Fri).

**Peak Day Load Balancing Advisory** *(auto-expands when overloaded days detected)* — stagger suggestions for peak conflict units.

**Advanced Insights:**
- **Capacity Breach Risk** — 🔴/🟡/🟢 risk tiers with P(breach), expected breach days/month, seats to add
- **Temporal Clusters** — groups units by attendance correlation > 0.7; "Apply Cluster-Diverse Placement" button

**Report Download** — Excel workbook (8 sheets: Executive Summary, Forecast Summary, Short-Term Forecast, DOW Patterns, Capacity Breach Risk, Load Balancing, Overflow Planning, Temporal Clusters).

### Tab 6 — 🗂️ Floor Plan Sandbox

Interactive floor layout editing isolated from the active scenario:

- Load the current scenario's floor assignments or upload an external layout (Excel/CSV)
- Edit via data editor + 4 quick actions (move unit, remove floor, add assignment, resize)
- **Impact Simulation** — shows how edits affect demand/supply balance
- **Re-Optimize** — runs LP optimizer on the sandbox layout
- **Accept & Push** — commits sandbox changes to the active scenario

### Tab 7 — ⚙️ Admin

- **Data Upload** — single Excel (3 tabs) or three separate files; "Load Sample Data" for instant demo
- **Edit Base Data** — modify floor capacities, unit headcounts, attendance & RTO data, per-unit seat alloc %; changes log to audit trail
- **Rule Configuration** — Global Allocation %, policy bounds (min/max %), RTO alert threshold
- **Audit Trail** — full change log with export to CSV

---

## LP Optimizer

The optimizer uses PuLP (CBC solver, 10-second time limit) to assign seats to physical floors.

**Objective:** Minimize floors used + cross-building splits + shortfall; reward adjacent floor pairs + location cohesion.

**Constraints:**
- Floor capacity (hard cap)
- Unit demand cap (units get at most what they need)
- Max floors per unit *(optional)*
- Tower restrictions — pin units to specific towers *(optional)*
- Minimum seat guarantee % *(optional, relaxed if infeasible)*

**Placement preference:**
1. Same floor (best — adjacency bonus 100)
2. Adjacent floors in same tower (bonus 60)
3. Same tower (bonus 30)
4. Same building (bonus 15)
5. Cross-building (bonus 0, penalized)

---

## Configuration

### `config/defaults.py` key constants

| Constant | Default | Description |
|----------|---------|-------------|
| `DEFAULT_GLOBAL_ALLOC_PCT` | 0.80 | Default global seat allocation % |
| `MIN_ALLOC_PCT` | 0.20 | Floor allocation % |
| `MAX_ALLOC_PCT` | 1.50 | Cap allocation % |
| `PEAK_BUFFER_MULTIPLIER` | 1.0 | Multiplier for peak buffer in RTO demand |
| `SHRINK_CONTRIBUTION_FACTOR` | 0.5 | Fraction of shrinkage released to scarcity pool |
| `FLOOR_SATURATION_THRESHOLD` | 0.90 | Alert when floor > 90% used |
| `COMPARISON_MAX_COMBINATIONS` | 12 | Max scenario matrix combinations |
| `HW_MIN_PERIODS` | 12 | Min observations to attempt Holt-Winters |
| `FORECAST_CAPACITY_ALERT_THRESHOLD` | 0.90 | Days above this % trigger overflow alert |

---

## Project Structure

```
cpg_planning_tool/
├── app.py                          # Streamlit entry point (7 tabs)
├── requirements.txt
├── config/
│   ├── defaults.py                 # Policy bounds, constants, thresholds
│   └── ai_config.py                # Gemini API integration (optional AI brief)
├── models/                         # Data models (Floor, Unit, Scenario, etc.)
├── data/
│   ├── loader.py                   # File parsing (buildings, units, attendance, daily CSV)
│   ├── validator.py                # Cross-file validation
│   ├── session_store.py            # All st.session_state read/write
│   └── sample_data.py              # Synthetic demo data generators
├── engine/
│   ├── allocation_engine.py        # Seat demand computation + scarcity redistribution
│   ├── optimizer.py                # LP floor assignment (PuLP/CBC)
│   ├── scenario_engine.py          # Override application + simulation pipeline
│   ├── spatial.py                  # Floor scoring, adjacency, fragmentation
│   ├── forecasting.py              # Holt-Winters ETS, bootstrap CI, DOW patterns, clustering
│   ├── scenario_comparison.py      # Batch scenario matrix runner + composite ranking
│   ├── report_generator.py         # Excel scenario report
│   ├── demand_report_generator.py  # Excel demand analytics report (8 sheets)
│   ├── holistic_report_generator.py # Executive consolidated Excel report
│   └── holistic_pdf_report_generator.py # Executive consolidated PDF report
├── tabs/
│   ├── tab_executive_dashboard.py
│   ├── tab_optimization.py         # What-If Analysis (overrides + LP optimizer + matrix)
│   ├── tab_spatial_floor.py
│   ├── tab_unit_impact.py
│   ├── tab_forecasting.py          # Demand Analytics (HW forecasting, DOW, clustering, etc.)
│   ├── tab_floor_sandbox.py        # Interactive floor layout sandbox
│   └── tab_admin_governance.py
├── components/
│   ├── charts.py                   # Plotly charts
│   ├── comparison_charts.py        # Multi-scenario comparison charts
│   ├── floor_map.py                # Floor treemap grid renderer
│   ├── sidebar.py
│   ├── tables.py
│   └── metrics_cards.py
├── tests/                          # pytest unit tests
└── sample_files/                   # Pre-generated CSV/Excel files for testing
```

---

## Optional: AI Executive Brief

Requires a Google Gemini API key to enable a plain-English narrative on the Executive Dashboard.

**In-app:** Admin tab → scroll to bottom → "🔧 Advanced Settings — AI Configuration" → paste key.

**Environment variable:**
```bash
export GEMINI_API_KEY=your_key_here
streamlit run app.py
```

```bash
pip install google-generativeai
```

---

## Running Tests

```bash
pytest tests/ -v
```
