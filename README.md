# CPG Seat Planning & Scenario Intelligence Platform

A behavior-aware, scenario-driven seat planning and optimization tool for Companies & Properties Group (CPG). Replaces static allocation ratios with attendance-aware, growth-aware seat planning.

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

The column requirements are the same regardless of which upload option you use.

### File 1: Building & Floor Master (Required)

Defines physical seat supply. **One row per floor.**

| Column | Description | Example |
|--------|-------------|---------|
| `Building ID` | Unique building identifier | B1 |
| `Building Name` | Human-readable building name | HQ Campus |
| `Tower ID` | Unique tower identifier | B1-T1 |
| `Floor Number` | Floor number within the tower | 3 |
| `Total Seats` | Number of available seats on this floor | 120 |

Example CSV:

```csv
Building ID,Building Name,Tower ID,Floor Number,Total Seats
B1,HQ Campus,B1-T1,1,100
B1,HQ Campus,B1-T1,2,120
B1,HQ Campus,B1-T2,1,80
```

### File 2: Unit Headcount & Forecast (Required)

Defines demand drivers and planning assumptions. **One row per business unit.**

| Column | Description | Example |
|--------|-------------|---------|
| `Unit Name` | Business unit name | Engineering |
| `Current Total Headcount` | Current total HC for the unit | 400 |
| `HC Growth Forecast (%)` | Expected growth % over planning horizon | 15 |
| `Attrition Forecast (%)` | Expected attrition % over planning horizon | 8 |
| `Business Priority` | *(Optional)* High, Medium, or Low — used for scarcity prioritization | High |

Example CSV:

```csv
Unit Name,Current Total Headcount,HC Growth Forecast (%),Attrition Forecast (%),Business Priority
Engineering,400,15,8,High
Sales,300,5,12,Medium
Finance,80,2,3,Low
```

### File 3: Attendance & RTO Behavior (Required)

Enables behavior-aware allocation. **One row per business unit.** Unit names must match File 2.

| Column | Description | Example |
|--------|-------------|---------|
| `Unit Name` | Must match the Unit Name in the headcount file | Engineering |
| `Monthly Median In-Office Strength` | Median number of employees in-office per month | 250 |
| `Monthly Max In-Office Strength` | Peak number of employees in-office per month | 320 |
| `Avg RTO Days/Week` | Average return-to-office days per week (0–5) | 3.5 |
| `Attendance Stability` | *(Optional)* Stability score from 0 to 1 (1 = very stable) | 0.8 |

Example CSV:

```csv
Unit Name,Monthly Median In-Office Strength,Monthly Max In-Office Strength,Avg RTO Days/Week,Attendance Stability
Engineering,250,320,3.5,0.80
Sales,180,240,3.0,0.55
Finance,55,65,4.0,0.90
```

---

## Using the Application

### Sidebar (Global Controls)

- **Active Scenario** — switch between baseline and custom scenarios
- **Planning Horizon** — 3 or 6 months

### Tab 1: Executive Dashboard

Read-only summary for leadership review. Shows:
- **Effective supply** — reflects scenario adjustments (excluded floors, capacity reduction). Shows both base and effective seat counts when a scenario modifies supply.
- Seat gap and number of impacted units
- Capacity vs demand chart by tower
- Planning alerts (saturated floors, unit shortfalls, high fragmentation, RTO utilization)
- Stale-data warning when base data has changed since the last simulation

### Tab 2: Unit Impact View

Detailed per-unit analysis. Filter by priority, risk level, or unit name. Each unit shows:
- Current and projected headcount
- Recommended allocation % with explanation
- Effective demand vs allocated seats
- Gap and fragmentation score
- Risk level (RED / AMBER / GREEN)
- **RTO Status** (Aligned / Under-allocated / Under-utilized)

Select a unit to see the step-by-step allocation explanation and floor assignments.

### Tab 3: Spatial / Floor View

Physical seat utilization across towers and floors:
- Floor utilization bar chart (filter by tower)
- Unit-by-floor heatmap showing seat distribution
- Floor detail table with unit breakdown
- Consolidation suggestions for fragmented units

### Tab 4: Scenario Lab

Create and test "what-if" scenarios:

1. Adjust **scenario-wide controls**: global RTO mandate, capacity reduction, excluded floors
2. Edit **unit-level overrides**: growth %, attrition %, RTO days (advanced mode), allocation % — pre-filled with baseline values, edit only what you need
3. Click **"Run Simulation"** to compute results (or **"Reset Scenario"** to clear all overrides)

After simulation, the Scenario Lab shows:
- **Results table** — per-unit allocation, demand, gap, fragmentation
- **Scenario Impact Summary** — English narrative with overall stats, per-unit highlights, key risks, and RTO utilization alerts
- **Changes vs Baseline** — automatic comparison showing which units gained/lost seats, net change, and a side-by-side table with chart

A stale-data warning appears when base data has changed since the last simulation. Scenario changes are isolated — they never modify the baseline.

### Tab 5: Optimization & Recommendations

LP-based seat optimization using PuLP. The optimizer respects scenario adjustments — excluded floors and capacity reductions are applied before optimization.

Choose an objective:
- **Minimize Seat Shortfall** — reduce total unmet demand
- **Maximize Floor Cohesion** — keep units on same/adjacent floors
- **Minimize Floors Used** — consolidate onto fewer floors
- **Fair Allocation** — minimize worst-case shortfall ratio

Review active constraints (effective floor count and supply after scenario adjustments), then run. After running, review the before/after comparison. Click **"Accept & Apply"** to apply results to the active scenario.

### Tab 6: Admin & Governance

- **Data Upload** — upload a single Excel file (3 tabs) or three separate files, or load sample data
- **Edit Base Data** — modify floor capacities, unit headcounts, and per-unit seat allocation %
- **Rule Configuration** — choose allocation mode (Simple/Advanced), set global allocation %, adjust policy bounds, set RTO utilization alert threshold
- **Scenario Management** — create, lock, unlock, or delete scenarios
- **Audit Trail** — view and export a log of all changes, overrides, and actions

---

## Allocation Modes

The application supports two allocation modes, selectable in **Admin & Governance > Rule Configuration**.

### Simple Mode (Default)

Best for quick POCs and business discussions. Each unit is allocated a flat percentage of their headcount as seats.

| Step | Formula | Example |
|------|---------|---------|
| 1. **Base allocation %** | Global default (e.g., 80%) or per-unit override | 80% |
| 2. **Growth/attrition adjustment** | Base % × (1 + net HC change × months / 12) | 80% × 1.035 = 82.8% |
| 3. **Policy clamp** | Clamped to [min, max] allocation bounds | 82.8% (within bounds) |
| 4. **Effective demand** | Clamped % × Current headcount | 82.8% × 400 = 331 seats |

**Key settings:**
- **Global Seat Allocation %** (default 80%) — the company-wide default. Set in Rule Configuration.
- **Per-unit Seat Alloc %** — override the global default for specific units (e.g., Engineering at 90%). Set in Edit Base Data > Unit Headcount > "Seat Alloc %" column. Leave blank to use the global default.

Attendance data (median, peak, RTO, stability) is still uploaded and shown in dashboards, but is **not used** for allocation calculation in Simple mode. However, RTO data **is used** for utilization alerts (see [RTO Utilization Alerts](#rto-utilization-alerts) below).

### Advanced Mode

Full attendance-based formula for organizations that want behavior-aware planning. Toggle to "Advanced" in Rule Configuration to enable.

Uses a 6-step formula:
1. **Base demand** = Monthly median in-office strength / Total headcount
2. **Peak buffer** = (Max HC - Median HC) / Total HC, reduced for stable units
3. **RTO scaling** = Base demand × (Avg RTO days / 5)
4. **Growth adjustment** = Scaled demand × (1 + net HC change × months / 12)
5. **Final allocation %** = Growth-adjusted demand + peak buffer, clamped to policy bounds
6. **Effective demand (seats)** = Allocation % × Current headcount

Advanced mode shows additional configuration parameters for buffer and scaling (see below).

---

## Configuration Parameters

These are adjustable in **Admin & Governance > Rule Configuration**.

### Allocation Mode & Global Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Allocation Mode** | Simple | **Simple**: flat % allocation (global or per-unit). **Advanced**: derives allocation from attendance data. |
| **Global Seat Allocation %** | 80% | The company-wide default seat allocation as a percentage of headcount. Used as the base in Simple mode. Per-unit overrides (set in Edit Base Data) take precedence. |

### Allocation Policy Bounds

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Minimum Allocation %** | 20% | The lowest allocation percentage any unit can receive. Even if a unit's calculated demand is very low, it won't go below this floor. Prevents units from being effectively zeroed out. |
| **Maximum Allocation %** | 150% | The highest allocation percentage any unit can receive. Caps over-allocation for fast-growing or peak-heavy units. Values above 100% mean the unit gets more seats than its current headcount. |

### Buffer & Scaling Parameters (Advanced Mode Only)

These parameters are only visible and used when Allocation Mode is set to "Advanced".

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Stability Discount Threshold** | 0.70 | Units with attendance stability above this value are considered "stable" and receive a reduced peak buffer. Stable units have predictable attendance, so less buffer is needed for peak days. |
| **Stability Discount Factor** | 30% | How much to reduce the peak buffer for stable units. A value of 30% means stable units get 30% less peak buffer than volatile units. |
| **Peak Buffer Multiplier** | 1.0 | Scales the peak buffer up or down for all units. Increase above 1.0 to be more conservative (more buffer for peak days). Decrease below 1.0 to be leaner. |
| **Shrink Contribution Factor** | 0.50 | When there's scarcity, shrinking units (negative net HC change) release this fraction of their shrinkage back to the shared pool. A value of 0.50 means half of the projected reduction is made available to growing units. |

### RTO Utilization Alerts

The application monitors whether seat allocations are aligned with actual RTO/attendance behavior and flags mismatches. This works in **both** Simple and Advanced modes.

| Parameter | Default | Description |
|-----------|---------|-------------|
| **RTO Utilization Alert Threshold** | 20% | Alert when allocated seats exceed RTO-based expected need by this percentage. Units above this threshold are flagged as "Under-utilized". Configurable in Rule Configuration. |

**How expected seats are calculated:**

- **Simple mode**: `expected_seats = (avg_rto_days / 5) x current_hc`. Uses RTO days as a proxy for in-office presence.
- **Advanced mode**: `expected_seats = monthly_median_hc + stability-adjusted peak buffer`. Uses actual attendance data (median/max in-office strength, stability score) and the same buffer/stability parameters from the advanced allocation formula.

**Alert types:**

| Status | Condition | Meaning |
|--------|-----------|---------|
| **Under-allocated** | Allocated seats < expected need by >10% | Unit needs more seats to meet their RTO/attendance commitment |
| **Under-utilized** | Allocated seats > expected need by >threshold | Unit is not using its allocated space effectively |
| **Aligned** | Within bounds | Allocation matches RTO-based expected need |

Alerts appear in:
- **Executive Dashboard** — in the Planning Alerts table
- **Scenario Lab** — in the Scenario Impact Summary section
- **Unit Impact View** — as an "RTO Status" column on each unit

---

## Scenario Templates & Walkthroughs

The app includes 5 pre-built scenario templates available under **Admin & Governance > Quick-Create from Template**. Each comes with pre-configured overrides — just create it, switch to it in the sidebar, and click **Run Simulation** in the Scenario Lab.

### 1. RTO Mandate (4 days)

**Question it answers:** What happens to seat demand if we mandate 4 days/week in-office?

**What it does:** Sets a global RTO floor of 4 days/week. Units already at 4+ days are unaffected; units below 4 days get bumped up.

**How to run:**
1. Go to **Admin & Governance** > Quick-Create from Template > select **"RTO Mandate (4 days)"** > Create
2. Switch to this scenario in the sidebar
3. Go to **Scenario Lab** > click **Run Simulation**
4. Check the **Executive Dashboard** — seat gap will likely increase
5. Scroll down in Scenario Lab to see the auto-generated baseline comparison

### 2. Aggressive Growth

**Question it answers:** Can we absorb rapid team growth without running out of seats?

**What it does:** High-priority units (Engineering, Product) grow by 25%. All others grow by 10%. Attrition drops to 3%.

**How to run:**
1. Create from template > **"Aggressive Growth"**
2. Run Simulation in Scenario Lab
3. Check **Unit Impact View** — look for RED risk units with large shortfalls
4. Try **Optimization** with "Minimize Shortfall" to see the best possible allocation
5. Check the auto baseline comparison in Scenario Lab results

### 3. High Attrition / Downsizing

**Question it answers:** How many seats are freed up if we lose 15% of headcount across the board?

**What it does:** All units get 15% attrition and 0% growth — simulating a downturn or restructuring.

**How to run:**
1. Create from template > **"High Attrition / Downsizing"**
2. Run Simulation
3. Check **Spatial / Floor View** — look for surplus floors with low utilization
4. Try **Optimization** with "Minimize Floors Used" to identify which floors can be released entirely

### 4. Floor Consolidation (-20% capacity)

**Question it answers:** What if we give up 20% of our floor space (renovation, lease return)?

**What it does:** Reduces total seats on every floor by 20%. No unit overrides — just a supply reduction.

**How to run:**
1. Create from template > **"Floor Consolidation (-20% capacity)"**
2. Run Simulation
3. Check **Executive Dashboard** — the seat gap and impacted units count will jump
4. Try **Optimization** with "Fair Allocation" to distribute the pain equitably
5. Or go to Scenario Lab and manually exclude specific floors instead of a blanket reduction

### 5. Hybrid Efficiency (Low RTO)

**Question it answers:** How much seat sharing do we gain if everyone works mostly remote (2 days/week)?

**What it does:** All units drop to 2 RTO days/week. This dramatically reduces effective seat demand.

**How to run:**
1. Create from template > **"Hybrid Efficiency (Low RTO)"**
2. Run Simulation
3. Check **Spatial / Floor View** — you'll see many surplus floors
4. Try **Optimization** with "Minimize Floors Used" to consolidate onto fewer floors
5. Check baseline comparison in Scenario Lab results to see total seat savings

### Building Your Own Scenario

1. Go to **Admin & Governance** > Create Custom Scenario > give it a name and type
2. Switch to it in the sidebar
3. In the **Scenario Lab**:
   - Adjust **scenario-wide controls** (RTO mandate, capacity reduction, excluded floors)
   - Edit individual units in the override table (change growth %, attrition %, RTO days, or set an allocation % override)
4. Click **Run Simulation**
5. Browse results across Dashboard, Unit Impact, and Spatial tabs — baseline comparison appears automatically in the Scenario Lab results
6. Optionally run **Optimization** and accept results

### Editing Base Data

You can also modify the underlying baseline data directly in **Admin & Governance > Edit Base Data**:
- **Floor Capacities** — change Total Seats for any floor (e.g., after a renovation)
- **Unit Headcount** — update HC, growth %, attrition %, priority, or **Seat Alloc %** for any unit
  - **Seat Alloc %** is a per-unit allocation override used in Simple mode. Leave blank to use the global default. Example: set Engineering to 90% if they need more in-office seats than the company default.

Changes are logged in the audit trail. After editing base data, a warning banner appears in the Scenario Lab and Executive Dashboard reminding you to re-run the simulation. Changes take effect when you next run a simulation.

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
└── sample_files/           # Pre-generated CSV and Excel files for testing
```

Run tests with:

```bash
pytest tests/ -v
```
