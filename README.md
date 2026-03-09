# CPG Seat Planning & Scenario Intelligence Platform

A data-driven seat planning and optimization tool for Companies & Properties Group (CPG). Combines flat allocation rules with real attendance data (Median HC, Peak HC, RTO patterns) and LP optimization to find the best seat placement across buildings and floors.

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

1. Open the app and go to the **Admin** tab
2. Click **"Load Sample Data"** — a step-by-step progress panel loads 2 buildings, 20 floors, 8 business units, 90 days of attendance history, and pre-warms all tabs in one click
3. Go to **What-If Analysis** and click **"Run Policy Simulation"** to compute the baseline allocation
4. Explore results across all tabs — Executive Dashboard, Spatial/Floor View, Unit Impact View are all immediately populated
5. Go to **Demand Analytics** to explore Holt-Winters trend forecasts, short-term seat demand, DOW patterns, and the demand report download
6. *(Optional)* Go to **What-If Analysis** → expand **"Scenario Comparison Matrix"** → auto-run up to 24 scenario combinations and adopt the best

---

## Uploading Your Data

Upload your data via the **Admin** tab. You have two options:

### Option A: Single Excel File (Recommended)

Upload **one `.xlsx` file** with **3 sheets**. Name each sheet:

| Sheet | Accepted Names |
|-------|---------------|
| Buildings | `Buildings`, `Building Master`, `Floors`, `Floor Master` |
| Units | `Units`, `Headcount`, `Unit HC`, `Unit Headcount` |
| Attendance | `Attendance`, `RTO`, `RTO Behavior`, `Attendance & RTO` |

Sheet names are matched case-insensitively.

### Option B: Three Separate Files

Upload 3 individual files (CSV or single-sheet Excel), one for each dataset.

---

### Data Schemas

### File 1: Building & Floor Master (Required)

Defines physical seat supply. **One row per floor.**

| Column | Description | Example |
|--------|-------------|---------|
| `Building ID` | Unique building identifier | B1 |
| `Building Name` | Human-readable building name | HQ Campus |
| `Tower ID` | Unique tower identifier | B1-T1 |
| `Floor Number` | Floor number within the tower | 3 |
| `Total Seats` | Number of available seats on this floor | 120 |

### File 2: Unit Headcount & Forecast (Required)

Defines demand drivers and planning assumptions. **One row per business unit.**

| Column | Description | Example |
|--------|-------------|---------|
| `Unit Name` | Business unit name | Engineering |
| `Current Total Headcount` | Current total HC for the unit | 400 |
| `HC Growth Forecast (%)` | Expected net growth % over planning horizon (positive = growth, negative = downsizing) | 15 |
| `Business Priority` | *(Optional)* High, Medium, or Low — used for scarcity prioritization | High |
| `Night Shift %` | *(Optional)* Percentage of HC on night shift (0-100). Night-shift workers hot-seat on day-shift desks, reducing physical seat demand. Default: 0 | 10 |

### File 3: Attendance & RTO Behavior (Required)

Enables attendance-based validation. **One row per business unit.** Unit names must match File 2.

| Column | Description | Example |
|--------|-------------|---------|
| `Unit Name` | Must match the Unit Name in the headcount file | Engineering |
| `Monthly Median In-Office Strength` | Median number of employees in-office per month | 250 |
| `Monthly Max In-Office Strength` | Peak number of employees in-office per month | 320 |
| `Avg RTO Days/Week` | Average return-to-office days per week (0-5) | 3.5 |

---

## How Allocation Works

Each unit is allocated a flat percentage of their headcount as seats (default: 80%), adjusted for growth projections.

| Step | Formula | Example |
|------|---------|---------|
| 1. **Base allocation %** | Global default (e.g., 80%) or per-unit override | 80% |
| 2. **Growth adjustment** | Base % x (1 + Growth% x months / 12) | 80% x 1.035 = 82.8% |
| 3. **Policy clamp** | Clamped to [min, max] allocation bounds | 82.8% (within bounds) |
| 4. **Effective demand** | Clamped % x Current headcount | 82.8% x 400 = 331 seats |

### Night Shift & Hot-Seating

Units with a non-zero `Night Shift %` enable hot-seating (desk sharing between shifts):

| Step | Formula | Example (Engineering: 400 HC, 80% alloc, 10% night) |
|------|---------|------------------------------------------------------|
| 1. **Effective demand** | Alloc % x HC | 80% x 400 = 320 seats |
| 2. **Day demand** | Effective x (1 - Night%) | 320 x 0.90 = 288 seats |
| 3. **Night demand** | Effective x Night% | 320 x 0.10 = 32 seats |
| 4. **Physical demand** | max(Day, Night) | max(288, 32) = 288 seats |
| 5. **Hot-seat savings** | Effective - Physical | 320 - 288 = **32 seats saved** |

Night-shift workers reuse the same desks as day-shift workers. Only the larger shift determines physical seat requirements.

### Attendance-Based Validation

After allocation, the platform validates every unit's allocation against actual attendance behavior:

```
RTO Need = (Median HC + Peak Buffer) x (RTO Days / 5)
```

This tells you how many seats each unit *actually needs* based on real patterns. If allocation exceeds RTO Need, the unit is flagged as over-provisioned. If it's below, it's under-allocated.

### RTO Compliance

When a Global RTO Mandate is set (e.g., 3.5 days/week), units whose actual RTO is below the target are flagged as non-compliant.

---

## Using the Application

### Sidebar (Global Controls)

- **Active Scenario** — switch between baseline and custom scenarios; shows scenario type, lock status, override count, and last-run timestamp
- **Planning Horizon** — 3 or 6 months

### Tab 1: Executive Dashboard

Read-only summary for leadership review:
- **Scenario context caption** — always-visible line showing active scenario name, type, horizon, and last-run time
- **KPI cards** — effective supply, total demand, seat gap, units with shortfall
- **Key Insights** — up to 5 rule-based insight cards (🔴 risk / 💡 opportunity / 📊 neutral) surfacing the biggest shortfall, best consolidation opportunity, over-provisioned units, low-utilization floors, and RTO savings potential
- **Capacity vs Demand chart** by tower + utilization donut
- **Planning Alerts** with an alert summary badge (`🔴 N Capacity · 🟡 N RTO · ⚠️ N Other`); each category is a collapsible expander:
  - 🔴 **Capacity Alerts** — floor saturation, unit shortfalls
  - 🟡 **RTO Alerts** — allocated vs RTO-based need per unit (chart for all units; table for mismatches)
  - ⚠️ **Other Alerts** — fragmentation, cross-building spread
- **AI Executive Brief** *(hidden — Gemini API key required)* — collapsed expander at the bottom with a "Generate Brief" button that produces a 3-paragraph plain-English CFO narrative via Gemini 1.5 Flash
- Stale-data warning when base data has changed since the last simulation

### Tab 2: Unit Impact View

Detailed per-unit analysis. **🔴/🟡/🟢 count metric cards** above the table summarise risk distribution at a glance. Filter by priority, risk level, or unit name. Each unit shows:
- Current and projected headcount
- Recommended allocation % with explanation
- Effective demand vs allocated seats
- Gap, gap %, and fragmentation score
- Risk level (RED / AMBER / GREEN)
- RTO Status (Aligned / Under-allocated / Under-utilized)

A legend caption below the table explains Fragmentation, RTO Status, and Gap % definitions.

**Attendance Anomalies** *(expander)* — AI feature that flags units with statistically unusual attendance patterns (see [AI Features](#ai-features))

### Tab 3: Spatial / Floor View

Physical seat utilization across towers and floors. Two view modes via toggle:

**Charts view** (default):
- Floor utilization bar chart (filter by tower) with Utilization % colorbar
- Unit-by-floor heatmap showing seat distribution (zmin=0 baseline, Seats colorbar)

**Floor Map view**:
- Color-coded treemap blocks per floor showing each unit's seat allocation proportionally
- Grey "Available" blocks for unused capacity
- Consistent color palette across all floors for easy unit identification
- 2-column grid layout for quick visual overview

Both views share:
- Floor detail table showing **Largest Unit (N seats)** per floor
- Building spread analysis and consolidation suggestions for fragmented units

### Tab 4: Scenario Lab

The central hub for scenario creation and "what-if" analysis. At the top:

**Manage Scenarios** *(collapsible panel)*:
- View all scenarios with type, horizon, lock status, and creation time
- **Lock / Unlock** — protect a scenario from edits (shows 🔒 in sidebar selector)
- **Make Active →** — switch to a different scenario without leaving the tab
- **Delete (permanent)** — remove non-baseline, non-locked scenarios
- **Quick-Create from Template** — 5 pre-built scenario templates (see below)
- **Create Custom Scenario** — name, type, horizon, and description

Then, for the **active scenario**:

1. Adjust **scenario-wide controls**: global RTO mandate, excluded floors
2. Edit **unit-level overrides**: growth % (positive = expansion, negative = downsizing), allocation % override
3. Click **"Run Simulation"** to compute results

After simulation, the Scenario Lab shows:
- **4 summary metric cards** — Total Demand, Total Allocated, Net Gap, Units at Risk (above the results table)
- **Enriched results table** — per-unit columns with explicit source labelling:
  - `Policy Alloc %` — desk-ratio % from Admin rule (unchanged by optimizer)
  - `Effective Alloc %` — Allocated Seats ÷ Projected HC (reflects optimizer result)
  - `Policy Demand` — seats needed under the Admin rule
  - `Allocated Seats` — seats actually assigned (optimizer value after Accept & Apply)
  - `Gap (vs Policy)` — Allocated − Policy Demand (negative = shortfall)
  - When optimization has been applied, a blue banner clarifies which columns are rule-based vs optimizer-based
  - *Fragmentation (0–1)*: 0 = all on one floor (ideal); above 0.5 = consolidation opportunity
  - *How is Allocation % calculated?* — expandable formula with step-by-step walkthrough
- **Scenario Impact Summary** — overall stats, RTO Need explanation, per-unit highlights, key risks
- **Changes vs Baseline** — automatic comparison with side-by-side table and chart
- **Sensitivity Analysis** *(expander)* — AI feature that auto-varies key planning parameters to rank which levers impact seat gap most (see [AI Features](#ai-features))
- **Download Report** — two formats side by side:
  - **Excel (.xlsx)** — allocation, floor assignments, risks, optimization run
  - **PDF Boardroom Report (.pdf)** — professional multi-page report with: rule-based executive summary brief (no AI), color-coded tables (RED/AMBER/GREEN), KPI summary, floor utilization maps (treemap charts), floor assignments, risk narrative, hot-seating savings (if applicable), and optional optimization results page; ready to email to leadership

### Tab 5: What-If Analysis

Unified planning + optimization tab. **Run Simulation in Scenario Lab first** — the optimizer places units on floors based on demand computed by Simulation.

**Choose an optimization mode first** (drives which parameters are active):

| Mode | Demand basis | Alloc % used? | RTO slider |
|------|-------------|---------------|-----------|
| **Optimal Placement** | Headcount × Alloc % | Yes | Global RTO mandate |
| **RTO-Based** | Actual attendance data | No (greyed out) | Not used (greyed out) |
| **What-If RTO** | Attendance × target RTO | No (greyed out) | Target RTO level |

Irrelevant sliders are **greyed out** based on the selected mode with a contextual explanation banner.

**Planning Parameters** (all in one row):
- Global Alloc % (50–150%)
- Global RTO Mandate / Target RTO (0.5–5.0 days/week)
- Capacity Reduction % (0–30%)

**Placement Controls:**
- Max Floors Per Unit — cap how many floors any unit can spread across
- Minimum Seat Guarantee — ensure every unit gets at least X% of demand under scarcity

**Tower Restrictions** *(expander)* — pin specific units to chosen towers.

**Single "Simulate & Optimize" button** runs the full pipeline: simulation → LP optimizer → results.

**Combined Results Panel:**
- **Planning Impact** — Demand, Available Capacity, and Headroom vs baseline (shown when params change)
- **Optimization Status** — Optimal / Infeasible
- **Savings Summary** *(RTO modes)* — Policy-Based vs Attendance-Based seats, seats saved, floors freed
- **Before/After Comparison** — per-unit seats and floor count; cross-building splits flagged with warning
- **Cost Estimation** *(expander)* — annual cost and savings in dollars at a configurable $/seat/year rate
- **Consolidation Suggestions** — auto-generated opportunities
- **Optimization History** — last 3 runs for comparison
- **Accept & Apply** — commits demand params + floor assignments to active scenario; all other tabs update

**Sensitivity Analysis** — runs Lean/Balanced/Conservative buffer presets in parallel and compares seat demand range.

**Scenario Comparison Matrix** *(expander)* — automatically runs multiple parameter combinations and produces a ranked comparison report:
- Select parameter values to test: Alloc % values, RTO mandate values, Capacity Reduction values, Optimization Mode
- Live combination counter — blocked at 24 combinations max
- **Run All N Scenarios** — runs every combination through the full simulation + optimizer pipeline
- **Ranked results table** — all combinations sorted by composite score (headroom 35%, gap 35%, fragmentation 15%, consolidation 15%)
- **Best Scenario** callout with plain-English explanation
- **Demand/Capacity Chart** — grouped bar showing Demand, Capacity, Optimized Seats per scenario
- **Metrics Heatmap** — normalized RdYlGn matrix of all KPIs across all runs (green = better)
- **Adopt** any ranked scenario via dropdown → applies params + floor assignments to active scenario

**AI Insights** *(expanders)*:
- Attendance Anomalies — z-score anomaly detection (see AI Features)

**Placement preference (all objectives):**
1. Same floor (best)
2. Adjacent floors within the same tower — preferred when spreading across 2+ floors
3. Same tower
4. Same building
5. Cross-building — only when genuinely necessary; flagged with a warning

### Tab 6: Demand Forecasting (📈 Demand Analytics)

Data-driven forecasting from **daily attendance data** (CSV: Date, Unit Name, In-Office Count). Upload your own or use **"Load Sample Data"** in Admin for an instant 90-day demo (all tabs ready in one click).

**Attendance Trends & Forecast:**
- Unit selector (default: All Units combined) + forecast horizon slider (1–12 months)
- Line chart: historical scatter + 21-day EMA + Holt-Winters forecast curve + widening 95% confidence band
- **5 metric cards:** Current Median, Trend Slope (people/day), Residual Std, 6M Forecast, Model badge (Holt-Winters / Linear Reg.) + MAPE
- *How is this forecast projected?* expander — conditional text describing the active model
- **Model selection:** Holt-Winters Additive ETS (trend + damped growth + Mon–Fri weekly seasonality) used automatically when ≥ 12 weekday observations and < 20% data gaps exist; falls back to linear regression + EMA for sparse datasets

**Forecast Summary (All Units):**
- Table: Unit | Current Median | Current Peak | Forecast Median (6m) | 6M Change (seats) | 6M Change % | Trend (↑ Growing / → Stable / ↓ Declining)
- 6M Change % bounded ±100%; Forecast Median = end-of-period projected value, floored at 0
- **"Apply 6-Month Growth Estimate"** — pushes data-driven growth % into scenario unit overrides

**Short-Term Seat Demand Forecast:**
- Horizon options: 5 / 10 / 15 / 21 business days ("How many seats will we need?")
- Per-unit Holt-Winters ETS models; fallback to DOW median + slope per unit
- Holiday exclusion — configured dates automatically skipped
- Capacity risk threshold: alert when any day exceeds 90% capacity
- Color-coded bar chart: green (safe) / amber (moderate) / red (> threshold)
- **Per-unit breakdown** toggle — drill into which teams drive demand on each day

**Peak Day Overflow Planning** *(auto-shown when alert days exist):*
- Capacity risk days table with expected seats vs capacity
- Available overflow floors (spare seats by floor)
- Units with seat shortfall — targeted flex coordination guide

**Probabilistic Seat Demand:**
- Confidence slider: 90% / 95% / 99%
- Grouped bar: Peak vs Percentile demand per unit; Bootstrap Monte Carlo CIs

**Day-of-Week Patterns:**
- Heatmap: units × Mon–Fri, colored by median in-office count

**Peak Day Load Balancing Advisory** *(auto-expands when overloaded days detected):*
- Company-wide load bar chart by weekday; overloaded days in red
- Per-unit peak day table; cross-unit conflict detection
- Stagger suggestions: which units to shift and to which lighter day

**Advanced Insights** (2 sub-tabs):
- **Capacity Breach Risk** — risk-tiered table (🔴/🟡/🟢) with P(breach), expected breach days/month, seats to add, recommended action
- **Temporal Clusters** — groups units by attendance correlation > 0.7; plain-language cluster advisory + "Apply Cluster-Diverse Placement" button

**Report Download:**
- **Excel (.xlsx)** — 8 sheets: Executive Summary, Forecast Summary, Short-Term Forecast, DOW Patterns, Capacity Breach Risk, Load Balancing, Overflow Planning (conditional), Temporal Clusters
- **PDF (.pdf)** — matching 8-page PDF with KPI header, risk-colored tables, and recommended-action column on every sheet

### Tab 7: Admin

- **Data Upload** — single Excel file (3 tabs) or three separate files, or load sample data; required-column schema hint displayed under each uploader
- **Edit Base Data** — modify floor capacities, unit headcounts, attendance & RTO data, and per-unit seat allocation %
- **Rule Configuration** — set global allocation %, policy bounds, planning buffer level (Lean / Balanced / Conservative), RTO alert threshold
- **Audit Trail** — view and export a log of all changes, overrides, and actions
- **Advanced Settings — AI Configuration** *(hidden, collapsed by default)* — paste a Gemini API key to enable the AI Executive Brief feature for the current session; the key is stored in session memory only and never written to disk

---

## Configuration Parameters

Adjustable in **Admin > Rule Configuration**.

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Global Seat Allocation %** | 80% | Company-wide default seat allocation as % of headcount |
| **Minimum Allocation %** | 20% | Floor — no unit gets below this % |
| **Maximum Allocation %** | 150% | Cap — no unit gets above this % |
| **Planning Buffer** | Balanced | Lean / Balanced / Conservative — controls peak buffer and scarcity redistribution |
| **RTO Utilization Alert Threshold** | 20% | Alert when allocated seats exceed RTO-based need by this % |

### Planning Buffer Presets

| Preset | Peak Buffer Multiplier | Shrink Contribution Factor |
|--------|----------------------|---------------------------|
| Lean | 0.7 | 0.7 |
| Balanced | 1.0 | 0.5 |
| Conservative | 1.4 | 0.3 |

---

## Scenario Templates

5 pre-built templates available in **Scenario Lab > Manage Scenarios > Quick-Create from Template**:

1. **RTO Mandate (4 days)** — What happens if we mandate 4 days/week in-office?
2. **Aggressive Growth** — Can we absorb 25% growth in key units?
3. **Downsizing (-15% Growth)** — How many seats free up when headcount contracts by 15%?
4. **Floor Consolidation (Give Up Floors)** — What if we take 4 floors offline for sublease or renovation?
5. **Hybrid Efficiency (Low RTO)** — How much do we save at 2 days/week?

---

## AI Features

Five analytical AI features are built into the platform — no external API or internet connection required. All computation runs locally using numpy, pandas, and scipy.

---

### 1. What-If Sensitivity Analysis *(Scenario Lab tab)*

**What it does:** Automatically identifies which planning levers have the biggest impact on your seat supply–demand gap. Answers: *"Should I focus on adjusting allocation %, the planning horizon, or the RTO mandate?"*

**How it works:**
1. Takes the current scenario as baseline and runs the full allocation pipeline to get a reference seat gap
2. Varies one parameter at a time (classic one-at-a-time sensitivity method), keeping all others fixed
3. Re-runs the full allocation pipeline for each variation and records the resulting gap
4. Ranks all variations by absolute impact on seat gap

**Parameters tested:**

| Parameter | Variations |
|-----------|-----------|
| Global Allocation % | −10%, −5%, +5%, +10% from current |
| Planning Horizon | −6 months, −3 months, +3 months, +6 months |
| Capacity Reduction | 0%, 5%, 10%, 15% of total floor capacity |
| RTO Mandate | −1.0, −0.5, +0.5, +1.0 days/week |

**What you see:**
- **Tornado chart** — horizontal bars sorted by impact magnitude; green = tightens gap, red = widens gap
- **Parameter impact ranking table** — which parameter has the widest swing across its tested range
- **Detailed results table** (expandable) — every variation with before/after gap values

> **Note:** Each click runs ~16 full allocation simulations. Expect 2–5 seconds for typical datasets.

---

### 3. Attendance Anomaly Detection *(Unit Impact View tab + Executive Dashboard)*

**What it does:** Flags units with statistically unusual attendance patterns that may indicate bad planning assumptions, data quality issues, or significant hot-desking opportunities. Uses z-scores so results adapt to your specific dataset.

**How it works:**
1. Compute 3 metrics per unit from the attendance data
2. Calculate the z-score for each metric: `(value − mean) / std_dev`
3. Flag any unit where a metric is more than **2 standard deviations** from the group mean
4. Requires at least 3 units with attendance data for meaningful statistics

**Metrics checked:**

| Metric | What it flags | Anomaly direction |
|--------|--------------|-------------------|
| **Peak-to-Median Ratio** | How spiky is attendance? | High = very spiky (buffer risk); Low = very flat |
| **Avg RTO Days/Week** | How often does the unit come in? | High = always in office (check if over-seated); Low = rarely in (hot-desk candidate) |
| **Median HC / Current HC** | Does attendance match headcount? | High = more people in office than HC suggests; Low = possible data quality issue |

**What you see:**
- Table of flagged units with metric, actual value, z-score, anomaly type, and recommendation
- Z-score coloring: amber = 2–3σ, red = >3σ
- Anomaly count surfaced in the Executive Dashboard **Other Alerts** card

**PDF report:** Attendance Anomalies page with color-coded rows.

---

---

### 4. Demand Forecasting *(Demand Analytics tab)*

**What it does:** Converts daily attendance records into statistical forecasts, probabilistic seat demand, and temporal patterns. Replaces manual growth % guesses with data-driven projections.

**Features:**
- **Holt-Winters ETS Trend Forecast** — Triple exponential smoothing (level + trend + Mon–Fri weekly seasonality, damped) on business-day-aligned data → wavy seasonal forecast curve + widening 95% PI; MAPE reported for model accuracy. Automatically falls back to linear regression + 21-day EMA for sparse/weekend-heavy data.
- **Short-Term Forecast (5–21 days)** — Per-unit HW models summed for aggregate seat demand; holiday-aware; per-unit breakdown toggle; capacity risk threshold alerts
- **Probabilistic Demand** — 90th/95th/99th percentile demand from historical distribution → quantifies seat savings vs. peak-based planning
- **Bootstrap Confidence Intervals** — 1000-resample Monte Carlo CI on percentile estimates
- **Day-of-Week Patterns** — median attendance by weekday per unit (reveals Tue/Wed peaks)
- **Capacity Breach Risk** — tiered risk table with `P(daily_attendance > allocated_seats)`, expected breach days/month, seats to add
- **Temporal Clustering** — groups units by attendance correlation > 0.7; drives cluster-diverse floor placement
- **Demand Analytics Report** — full Excel + PDF download with 8 sheets/pages and actionable recommended actions per insight

**Integration:** "Apply 6-Month Growth Estimate" writes data-driven growth % into scenario unit overrides. Re-run simulation to see updated demand.

---

### 5. Scenario Comparison Matrix *(What-If Analysis tab)*

**What it does:** Automatically runs a full grid of parameter combinations — allocation %, RTO mandate, capacity reduction, and optimization mode — and ranks all scenarios by a composite score. Eliminates manual slider-tweaking.

**How it works:**
1. User selects value sets for each parameter (e.g., Alloc % = [70%, 80%, 90%], Cap Red = [0%, 10%])
2. `itertools.product` generates all combinations (capped at 24 to keep runtime < 10 seconds)
3. Each combination runs through the full `run_scenario()` + `optimize_allocation()` pipeline
4. Results are scored on 4 dimensions (normalized 0–1, higher = better):
   - **Headroom** (35%) — capacity headroom above demand
   - **Gap** (35%) — no shortfall = full score; negative gap = proportional penalty
   - **Fragmentation** (15%) — lower avg fragmentation score = higher score
   - **Consolidation** (15%) — fewer floors used = higher score
5. Best scenario is highlighted with a plain-English explanation

---

### 6. Temporal Demand Clustering *(Demand Forecasting tab — Advanced Insights)*

**What it does:** Groups business units by similar temporal attendance patterns to identify hot-desking and shared floor-assignment opportunities — complementing attendance-pattern analysis with temporal grouping.

**How it works:**
1. Pivot daily attendance into a unit × date matrix
2. Compute pairwise Pearson correlation
3. Single-pass threshold clustering: units with correlation > 0.7 are grouped together
4. Same-cluster units have correlated daily demand — they peak and trough together

---

### Configuring AI Feature Thresholds

All AI feature parameters are in `config/defaults.py`:

```python
# Sensitivity analysis parameter ranges
SENSITIVITY_ALLOC_VARIATIONS = [-0.10, -0.05, 0.05, 0.10]
SENSITIVITY_HORIZON_VARIATIONS = [-6, -3, 3, 6]
SENSITIVITY_CAPACITY_REDUCTIONS = [0.0, 0.05, 0.10, 0.15]
SENSITIVITY_RTO_VARIATIONS = [-1.0, -0.5, 0.5, 1.0]

# Anomaly detection
ANOMALY_Z_SCORE_THRESHOLD = 2.0    # Standard deviations to flag
ANOMALY_MIN_UNITS = 3              # Minimum units required for z-scores

# Demand Forecasting
FORECAST_DEFAULT_MONTHS = 6
FORECAST_CONFIDENCE_LEVELS = [0.90, 0.95, 0.99]
FORECAST_BOOTSTRAP_SAMPLES = 1000
FORECAST_EMA_SPAN = 21
HW_MIN_PERIODS = 12        # Min observations to attempt Holt-Winters fit
HW_SEASONAL_PERIODS = 5    # Business week (Mon-Fri)

# Scenario Comparison Matrix
COMPARISON_MAX_COMBINATIONS = 24
COMPARISON_ALLOC_OPTIONS = [0.60, 0.70, 0.80, 0.90, 1.00]
COMPARISON_RTO_OPTIONS = [2.0, 2.5, 3.0, 3.5, 4.0]
COMPARISON_CAPRED_OPTIONS = [0.0, 0.05, 0.10, 0.15, 0.20]
```

---

## Project Structure

```
cpg_planning_tool/
├── app.py                       # Streamlit entry point (7 tabs)
├── requirements.txt             # Python dependencies
├── config/
│   ├── defaults.py              # Policy bounds, constants, AI feature thresholds
│   └── ai_config.py            # Gemini API integration (hidden AI brief feature)
├── models/                      # Data models (Floor, Unit, Scenario, DailyAttendanceRecord, etc.)
├── data/                        # File loader, validator, session store, sample data
├── engine/
│   ├── allocation_engine.py     # Seat demand computation and scarcity redistribution
│   ├── optimizer.py             # LP-based floor assignment (PuLP)
│   ├── scenario_engine.py       # Scenario cloning, override application, simulation pipeline
│   ├── spatial.py               # Floor scoring, adjacency, fragmentation
│   ├── explainer.py             # Human-readable allocation explanation steps
│   ├── sensitivity.py           # AI: one-at-a-time parameter sensitivity analysis
│   ├── anomaly.py               # AI: z-score attendance anomaly detection
│   ├── forecasting.py           # AI: demand forecasting (Holt-Winters ETS, EMA, bootstrap CI, clustering)
│   ├── scenario_comparison.py   # AI: batch scenario matrix runner + composite ranking
│   ├── report_generator.py      # Excel report export (What-If Analysis)
│   ├── pdf_report_generator.py  # PDF boardroom report (What-If Analysis)
│   ├── demand_report_generator.py    # Excel demand analytics report (8 sheets)
│   └── demand_pdf_report_generator.py # PDF demand analytics report (8 pages)
├── tabs/                        # All 7 UI tabs
│   ├── tab_executive_dashboard.py
│   ├── tab_unit_impact.py
│   ├── tab_spatial_floor.py
│   ├── tab_scenario_lab.py
│   ├── tab_optimization.py      # What-If Analysis (unified mode + Scenario Comparison Matrix)
│   ├── tab_forecasting.py       # Demand Forecasting (new in Round 18)
│   └── tab_admin_governance.py
├── components/
│   ├── charts.py                # All Plotly charts
│   ├── comparison_charts.py     # Multi-scenario comparison charts (new in Round 19)
│   ├── sidebar.py
│   ├── tables.py
│   └── floor_map.py
├── tests/                       # Unit tests (pytest)
├── docs/                        # Executive summary and documentation
└── sample_files/                # Pre-generated CSV and Excel files for testing
```

### Optional: AI Executive Brief

To enable the Gemini-powered AI narrative on the Executive Dashboard, either:

- **Option A (in-app):** Open the Admin tab → scroll to the bottom → expand "🔧 Advanced Settings — AI Configuration" → paste your Gemini API key → click "Enable AI Feature". The key lives in the session only.
- **Option B (env var):** Set `GEMINI_API_KEY` in your environment before launching:
  ```bash
  export GEMINI_API_KEY=your_key_here
  streamlit run app.py
  ```

Install the optional dependency:
```bash
pip install google-generativeai
```

Run tests with:

```bash
pytest tests/ -v
```
