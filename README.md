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

1. Open the app and go to the **Admin & Governance** tab
2. Click **"Load Sample Data"** to load pre-built test data (2 buildings, 20 floors, 8 business units)
3. Go to **Scenario Lab** and click **"Run Simulation"** to compute the baseline allocation
4. Explore results across all tabs

---

## Uploading Your Data

Upload your data via the **Admin & Governance** tab. You have two options:

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
| `HC Growth Forecast (%)` | Expected growth % over planning horizon | 15 |
| `Attrition Forecast (%)` | Expected attrition % over planning horizon | 8 |
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

Each unit is allocated a flat percentage of their headcount as seats (default: 80%), adjusted for growth and attrition projections.

| Step | Formula | Example |
|------|---------|---------|
| 1. **Base allocation %** | Global default (e.g., 80%) or per-unit override | 80% |
| 2. **Growth/attrition adjustment** | Base % x (1 + net HC change x months / 12) | 80% x 1.035 = 82.8% |
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

- **Active Scenario** — switch between baseline and custom scenarios
- **Planning Horizon** — 3 or 6 months

### Tab 1: Executive Dashboard

Read-only summary for leadership review:
- **KPI cards** — effective supply, total demand, seat gap, units with shortfall
- **Capacity vs Demand chart** by tower + utilization donut
- **Grouped Planning Alerts**:
  - Capacity alerts (floor saturation, unit shortfalls)
  - RTO alerts chart (allocated vs RTO need per unit) with mismatch table
  - Other alerts (fragmentation, cross-building spread)
- Stale-data warning when base data has changed since the last simulation

### Tab 2: Unit Impact View

Detailed per-unit analysis. Filter by priority, risk level, or unit name. Each unit shows:
- Current and projected headcount
- Recommended allocation % with explanation
- Effective demand vs allocated seats
- Gap and fragmentation score
- Risk level (RED / AMBER / GREEN)
- RTO Status (Aligned / Under-allocated / Under-utilized)

### Tab 3: Spatial / Floor View

Physical seat utilization across towers and floors:
- Floor utilization bar chart (filter by tower)
- Unit-by-floor heatmap showing seat distribution
- Floor detail table with unit breakdown
- Consolidation suggestions for fragmented units

### Tab 4: Scenario Lab

Create and test "what-if" scenarios:

1. Adjust **scenario-wide controls**: global RTO mandate, capacity reduction, excluded floors
2. Edit **unit-level overrides**: growth %, attrition %, allocation % override
3. Click **"Run Simulation"** to compute results

After simulation, the Scenario Lab shows:
- **Enriched results table** — per-unit allocation, demand, gap, RTO Need, RTO Status, fragmentation
- **Scenario Impact Summary** — overall stats, RTO Need explanation, per-unit highlights, key risks
- **Changes vs Baseline** — automatic comparison with side-by-side table and chart

### Tab 5: Optimization & Recommendations

LP-based seat optimization using PuLP. Three business-relevant objectives:

- **Optimal Placement** — seat everyone per allocation rule on fewest floors with maximum cohesion
- **RTO-Based** — allocate by actual attendance patterns, free unused capacity. Shows seats saved and floors freed.
- **What-If RTO** — simulate a different RTO policy (slider: 1-5 days/week). See "If everyone came in 4 days, here's what we'd need."

The optimizer:
- Caps each unit at their demand (respects the global allocation rule)
- Minimizes floors used + maximizes team cohesion (same/adjacent floors)
- Shows before/after comparison with savings metrics
- "Accept & Apply" pushes results to all other tabs

### Tab 6: Admin & Governance

- **Data Upload** — single Excel file (3 tabs) or three separate files, or load sample data
- **Edit Base Data** — modify floor capacities, unit headcounts, attendance & RTO data, and per-unit seat allocation %
- **Rule Configuration** — set global allocation %, policy bounds, planning buffer level (Lean / Balanced / Conservative), RTO alert threshold
- **Scenario Management** — create, lock, unlock, or delete scenarios
- **Audit Trail** — view and export a log of all changes, overrides, and actions

---

## Configuration Parameters

Adjustable in **Admin & Governance > Rule Configuration**.

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

5 pre-built templates available under **Admin & Governance > Quick-Create from Template**:

1. **RTO Mandate (4 days)** — What happens if we mandate 4 days/week in-office?
2. **Aggressive Growth** — Can we absorb 25% growth in key units?
3. **High Attrition / Downsizing** — How many seats free up with 15% attrition?
4. **Floor Consolidation (-20%)** — What if we lose 20% floor space?
5. **Hybrid Efficiency (Low RTO)** — How much do we save at 2 days/week?

---

## Project Structure

```
cpg_planning_tool/
├── app.py                  # Streamlit entry point
├── requirements.txt        # Python dependencies
├── config/defaults.py      # Policy bounds and constants
├── models/                 # Data models (Floor, Unit, Scenario, etc.)
├── data/                   # File loader, validator, session store, sample data
├── engine/                 # Allocation, spatial, scenario, optimizer, explainer
├── tabs/                   # All 6 UI tabs
├── components/             # Sidebar, charts, metric cards, tables
├── tests/                  # Unit tests (pytest)
├── docs/                   # Executive summary and documentation
└── sample_files/           # Pre-generated CSV and Excel files for testing
```

Run tests with:

```bash
pytest tests/ -v
```
