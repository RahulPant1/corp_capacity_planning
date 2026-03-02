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
2. Click **"Load Sample Data"** to load pre-built test data (2 buildings, 20 floors, 8 business units)
3. Go to **Scenario Lab** and click **"Run Simulation"** to compute the baseline allocation
4. Explore results across all tabs

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

### Tab 3: Spatial / Floor View

Physical seat utilization across towers and floors:
- Floor utilization bar chart (filter by tower) with Utilization % colorbar
- Unit-by-floor heatmap showing seat distribution (zmin=0 baseline, Seats colorbar)
- Floor detail table showing **Largest Unit (N seats)** per floor (replaces the old concatenated "Units (seats)" cell)
- Consolidation suggestions for fragmented units

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
- **Download Report** — two formats side by side:
  - **Excel (.xlsx)** — allocation, floor assignments, risks, optimization run
  - **PDF Boardroom Report (.pdf)** — professional 5-page report with color-coded tables (RED/AMBER/GREEN), KPI summary, floor assignments, risk narrative, and optional optimization results page; ready to email to leadership

### Tab 5: Optimization & Recommendations

LP-based seat optimization using PuLP. **Run Simulation first** — Optimization places units on floors based on demand computed by Simulation.

**Three objectives:**
- **Optimal Placement** — seat everyone per allocation rule on fewest floors with maximum cohesion
- **RTO-Based** — allocate by actual attendance patterns, free unused capacity. Shows seats saved and floors freed.
- **What-If RTO** — simulate a different RTO policy (slider: 1-5 days/week)

**Placement preference (all objectives):** The optimizer strongly prefers to keep each unit consolidated:
1. **Same floor** (best) — unit stays on a single floor
2. **Adjacent floors** — when spreading across 2+ floors, consecutive floors within the same tower are preferred over non-consecutive (e.g., floors 3 & 4 over floors 1 & 4)
3. **Same tower** — before spreading to another tower
4. **Same building** — before crossing to another building
5. **Cross-building** — only when a single building genuinely lacks capacity; flagged with a warning in results

**Scenario Settings in Effect** *(expander)* — shows active scenario-level constraints (RTO mandate, excluded floors, floor capacity) before running.

**Runtime Constraints (Optional)** *(expander)* — applied at run time on top of the objective:
- **Max Floors Per Unit** — cap how many floors any unit can spread across (e.g., max 2 floors); adjacent floors are always preferred within that budget
- **Pin Units to Tower** — restrict specific units to a tower (e.g., Engineering stays in B1-T1)
- **Minimum Seats Guarantee** — ensure every unit gets at least X% of their demand even under scarcity

**Results include:**
- **Policy-Based Seats (80% Rule)** vs **Attendance-Based Seats** summary metrics (RTO objectives)
- Before/after seat and floor count comparison per unit; cross-building splits flagged with a warning
- **Cost Estimation Panel** — enter $ per seat/year to see annual cost and savings in dollars
- **Optimization History** — last 3 runs stored for comparison (objective, seats, floors used)
- **Sensitivity Analysis** — auto-runs Lean/Balanced/Conservative buffer presets and shows seat demand range
- "Accept & Apply" pushes results to Dashboard, Spatial View, and Unit Impact

### Tab 6: Admin

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

## Project Structure

```
cpg_planning_tool/
├── app.py                       # Streamlit entry point
├── requirements.txt             # Python dependencies
├── config/
│   ├── defaults.py              # Policy bounds and constants
│   └── ai_config.py            # Gemini API integration (hidden AI brief feature)
├── models/                      # Data models (Floor, Unit, Scenario, etc.)
├── data/                        # File loader, validator, session store, sample data
├── engine/
│   ├── ...                      # Allocation, spatial, scenario, optimizer, explainer
│   └── pdf_report_generator.py  # PDF boardroom report (reportlab)
├── tabs/                        # All 6 UI tabs
├── components/                  # Sidebar, charts, metric cards, tables
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
