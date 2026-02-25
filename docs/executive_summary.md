# Intelligent Seat Planning: Using Data & Analytics to Optimize CPG Real Estate

---

## Slide 1: Executive Summary

### The Challenge

CPG currently allocates office seats using static rules — typically a flat percentage of unit headcount (e.g., 80%). While simple, this approach creates significant inefficiencies:

- **Over-provisioning**: Some units receive more seats than their actual attendance patterns require
- **Under-utilization**: Allocated floors sit partially empty because real attendance is lower than the rule assumes
- **No visibility**: No way to compare what's allocated vs. what's actually used, or to model the impact of changes
- **Manual planning**: Scenarios (growth, floor closures, RTO policy changes) are modeled in spreadsheets — slow, error-prone, and not auditable

### The Solution

A **data-driven seat planning platform** that combines:

1. **CPG's allocation rules** (80% global allocation) with **real attendance data** (median headcount, peak days, RTO patterns)
2. **Mathematical optimization** (Linear Programming) to find the best seat placement across buildings and floors
3. **Scenario intelligence** for instant what-if modeling with before/after comparisons

### The Outcome

| Metric | Before (Spreadsheet) | After (Platform) |
|--------|---------------------|-------------------|
| Planning cycle | Weeks | Minutes |
| Allocation basis | Static rule only | Rule + attendance validation |
| Scenario modeling | Manual, one at a time | Instant, side-by-side comparison |
| Floor optimization | Not possible | LP-based, automated |
| Audit trail | None | Full change log |

---

## Slide 2: How Technology, Data & Analytics Improve Seat Allocation

### Three Pillars

#### 1. Data-Driven Allocation & Validation

Instead of relying solely on the 80% rule, the platform validates every allocation against **actual attendance behavior**:

- **Median HC**: How many people typically come in each month
- **Peak HC**: Surge capacity needed on the busiest days
- **RTO Days/Week**: How many days per week each unit actually attends office

**The formula**: `RTO Need = (Median HC + Peak Buffer) x (RTO Days / 5)`

This tells you exactly how many seats each unit *actually needs* — and where the 80% rule is over-allocating or under-allocating.

#### 2. Optimization Engine

A **Linear Programming optimizer** places units across floors to:

- **Minimize floors used** — consolidate teams onto fewer floors, freeing real estate
- **Maximize team cohesion** — keep units on the same or adjacent floors (same tower > same building > cross-building)
- **Respect constraints** — floor capacity limits, excluded floors, capacity reductions

Three optimization modes:
- **Optimal Placement**: Seat everyone per the allocation rule on the fewest possible floors
- **RTO-Based**: Allocate by actual attendance patterns — typically frees 20-40% of seats
- **What-If RTO**: "If everyone came in 4 days/week instead of 3, what changes?"

Advanced runtime constraints let planners control the optimizer without touching code:
- **Max floors per unit** — cap fragmentation by design (e.g., Sales on no more than 2 floors)
- **Pin units to a tower** — respect lease obligations, security zones, or equipment proximity
- **Minimum seats guarantee** — protect critical units from being squeezed under scarcity

Additional analytical tools:
- **Cost Estimation** — enter $/seat/year to instantly translate optimization results into dollar savings
- **Sensitivity Analysis** — auto-run Lean/Balanced/Conservative buffer assumptions and see the seat demand range
- **Optimization History** — compare last 3 runs side by side before committing

#### 3. Scenario Intelligence

Model any planning scenario in seconds:

- Adjust growth/attrition rates per unit
- Exclude floors (renovation, sublease)
- Change global RTO mandate
- Reduce capacity (social distancing, hot-desking ratios)

Every scenario shows:
- Before/after seat allocation per unit
- Risk alerts (shortfalls, fragmentation, RTO non-compliance)
- Automatic comparison vs. baseline

### Data Required

| Data Source | Examples | Refresh Frequency |
|-------------|----------|-------------------|
| HR / HRIS | Headcount, growth projections, attrition | Quarterly |
| Badge / Access Systems | Monthly median attendance, peak attendance, RTO days | Monthly |
| Facilities | Building/tower/floor structure, seat capacity | As-needed |
| Business Units | Priority ranking, allocation % overrides | Annual |

---

## Slide 3: Benefits, Costs & ROI

### Qualitative Benefits

| Benefit | Description |
|---------|-------------|
| **Real estate cost reduction** | RTO-based optimization typically reveals 20-40% fewer seats needed vs. flat rule. Potential to free entire floors for sublease or consolidation. |
| **Better employee experience** | Cohesion scoring keeps teams on same/adjacent floors instead of scattered across buildings. Reduces commute between meeting rooms. |
| **Faster planning cycles** | Scenarios that took weeks of spreadsheet coordination run in seconds. Planners can model 10 options in the time it took to do 1. |
| **Risk visibility** | Automated alerts: floor saturation, unit shortfalls, RTO non-compliance, cross-building fragmentation. No surprises. |
| **Audit trail & governance** | Every change is logged with timestamp, user, old/new value, and rationale. Supports compliance and decision review. |
| **Data-backed decisions** | Before/after comparisons for every scenario. Present to leadership with confidence, not gut feel. |

### Costs to Execute

| Item | Effort | Timeline |
|------|--------|----------|
| **Data collection** (one-time) | Gather attendance data from badge/HR systems, building floor plans, unit headcount | 2-4 weeks (Facilities + HR) |
| **Platform deployment** | Tool is built and ready. Deploy to cloud (Streamlit Cloud / internal hosting) | ~1 week |
| **Change management** | Train real estate planners and BU leads on the platform | 2-3 sessions |
| **Ongoing maintenance** | Quarterly data refresh (attendance, headcount). Minimal engineering. | ~2 hours/quarter |

### Illustrative ROI Calculation

| Parameter | Value |
|-----------|-------|
| Average seat cost (premium office, industry range) | $8,000 - $12,000 / year |
| Excess seats identified via RTO-based optimization (example) | 200 seats |
| **Annual direct savings** | **$1.6M - $2.4M** |
| Indirect savings (facilities overhead, energy, cleaning for freed floors) | Additional 10-15% |
| Implementation cost (one-time) | < $50K (data collection + deployment + training) |
| **Payback period** | **< 1 month** |

*Note: Actual savings depend on CPG's real estate portfolio size, current utilization rates, and lease terms. The platform quantifies exact numbers once real data is loaded.*

---

## Key Features to Highlight in Demo

### Feature 1: Scenario What-If Modeling (Scenario Lab)

> "What if Engineering grows 15% and we lose Floor 3 to renovation?"

- Adjust growth rates, attrition, excluded floors, capacity reduction — per unit or globally
- Run simulation in one click, see instant results
- Automatic comparison vs. baseline: which units gained/lost seats, net change
- Risk alerts flag issues before they become problems

### Feature 2: RTO-Based Optimization with Cost Translation (Optimization Tab)

> "Based on actual attendance, we can free 3 floors — saving $1.8M/year"

- **Allocated vs. RTO Need chart**: Visual comparison per unit showing where over-provisioning exists
- **Savings metrics**: Seats saved, floors freed, before/after floor count
- **What-If RTO slider**: Drag to 3 days or 4 days — see how floor needs change instantly
- **Cost Estimation Panel**: Enter $/seat/year → instantly see total annual cost and dollar savings
- **Sensitivity Analysis**: One click shows seat demand range across Lean/Balanced/Conservative assumptions
- **Accept & Apply**: One click to apply optimized plan back to scenario

### Feature 3: Executive Dashboard with Actionable Alerts

> "One screen to see if your seat plan is healthy"

- **Scenario context caption**: active scenario name, type, horizon, and last-run time — always visible below the KPI row
- **KPI cards**: Total supply, demand, seat gap, units with shortfall
- **Capacity vs. Demand chart**: By tower, at a glance
- **Utilization donut**: Overall seat utilization percentage
- **Planning Alerts** with alert summary badge (`🔴 N Capacity · 🟡 N RTO · ⚠️ N Other`); each category is a collapsible expander:
  - 🔴 Capacity Alerts — floor saturation, unit shortfalls
  - 🟡 RTO Alerts — under-utilized seats, under-allocated units (chart for all + mismatch table)
  - ⚠️ Other Alerts — fragmentation, cross-building spread

---

## Summary: Why This Matters

| Without the Platform | With the Platform |
|---------------------|-------------------|
| "We think 80% is right" | "Data shows we need 62% for Sales, 78% for Engineering" |
| "We might have extra floors" | "We can free floors 5, 8, and 12 — saving $1.8M/year" |
| "What if RTO changes?" | "Here's the exact impact on every unit and floor" |
| "Trust the spreadsheet" | "Full audit trail, scenario comparison, risk alerts" |

**The platform turns seat planning from a cost center exercise into a strategic real estate optimization capability.**

---

## One-Pager: Executive Overview

### 1. Idea Summary
CPG offices are over-allocated using static rules that ignore actual attendance. This platform uses real badge/HR data and mathematical optimization to right-size seat allocations, consolidate floors, and quantify savings — replacing spreadsheet planning with data-driven decisions in minutes.

### 2. Business Context
| Problem | Impact |
|---------|--------|
| Flat 80% rule allocates seats regardless of actual attendance | Floors sit 30-50% empty on average days |
| No way to model RTO policy changes, growth, or floor closures | Reactive planning; surprises at lease renewal |
| Manual spreadsheet process, no audit trail | Decisions lack transparency and are hard to defend |
| Teams scattered across floors with no cohesion logic | Productivity loss; unnecessary cross-floor commute |

### 3. Approach, Methodology & Implementation
- **Data inputs**: Headcount (HR/HRIS), attendance patterns (badge systems), building floor plans (Facilities) — refreshed quarterly
- **Allocation engine**: Flat % rule (e.g., 80%) adjusted for growth/attrition; validated against RTO Need formula `(Median HC + Peak Buffer) × (RTO Days / 5)`
- **LP Optimizer**: Minimizes floors used + maximizes team cohesion; supports 3 objectives (Optimal Placement, RTO-Based, What-If RTO) with runtime constraints (floor caps, tower pinning, demand guarantees)
- **Platform**: Web-based tool (Streamlit), deployable on internal cloud or Streamlit Cloud; no installation required for end users
- **Implementation timeline**: Data collection 2–4 weeks → Deployment ~1 week → Training 2–3 sessions

### 4. Financial Viability
| Item | Estimate |
|------|----------|
| Platform build | Complete — ready to deploy |
| One-time setup cost (data + deployment + training) | < $50,000 |
| Ongoing cost (quarterly data refresh) | Minimal — ~2 hrs/quarter engineering |
| Average seat cost (premium office space) | $8,000 – $12,000 / seat / year |
| Typical excess seats found via RTO-based optimization | 15–30% of total allocated |
| **Annual savings on 200 excess seats** | **$1.6M – $2.4M** |
| Payback period | **< 1 month** |

*The built-in Cost Estimation panel translates any optimization result directly into dollar savings — no separate financial modelling needed.*

### 5. Outcome
| Before | After |
|--------|-------|
| Static 80% rule, no validation | Allocation validated against real attendance data |
| Floors over-provisioned, under-used | RTO-based optimization frees 15–30% of seats |
| Planning takes weeks | Scenarios run in seconds; 10 options explored in the time of 1 |
| No audit trail | Full change log: who changed what, when, and why |
| "We think we need X seats" | "Data shows we need X seats — here's the cost if we're wrong" |
| Optimizer over-allocates | LP caps each unit at their demand; respects the allocation rule |

---

---

# 10-Minute Management Demo Script

> **Setup before the meeting:** Launch the app (`streamlit run app.py`), open it in a browser, and keep this script open on a second screen.

---

## Flow 1 — "What's the current state?" *(~2 minutes)*

**Goal:** Show that the platform gives instant visibility into seat health — something that currently doesn't exist.

**Steps:**

1. **Admin tab → Load Sample Data** *(0:15)*
   - Click **"Load Sample Data"**
   - *Say:* "This simulates 2 buildings, 4 towers, 20 floors, and 8 business units with their attendance patterns. In production, this comes from your HRIS and badge systems."

2. **Scenario Lab → Run Simulation** *(0:30)*
   - Go to **Scenario Lab** tab
   - Click **"Run Simulation"**
   - *Say:* "This computes the baseline seat allocation for every unit — applying the 80% rule adjusted for growth projections, then validating against actual attendance data."

3. **Executive Dashboard — KPI cards & alerts** *(1:15)*
   - Switch to **Executive Dashboard**
   - Point to the **scenario context caption** below the KPI row (scenario name, type, horizon, last run)
   - Point to the **KPI cards** (supply, demand, seat gap, units with shortfall)
   - Point to **Capacity vs. Demand chart** — show which towers are over- or under-used
   - Scroll to **Planning Alerts** — point to the **alert summary badge** (`🔴 N Capacity · 🟡 N RTO · ⚠️ N Other`), then click into the **🟡 RTO Alerts** expander to show the chart
   - *Say:* "This is the one screen leadership would see every planning cycle. The badge gives the 30-second read — [X] alerts across capacity, RTO, and other. Click into any category for details. Right now, we can see [X units] are over-provisioned vs. their actual attendance — seats we're paying for that no one uses."

---

## Flow 2 — "What if Engineering grows and we lose a floor?" *(~3 minutes)*

**Goal:** Show scenario modeling — the core differentiator vs. spreadsheets.

**Steps:**

1. **Scenario Lab → Manage Scenarios → Quick-Create from Template** *(0:30)*
   - Open the **Manage Scenarios** expander at the top of Scenario Lab
   - Select template **"Aggressive Growth"**
   - Click **"Create from Template"**
   - Then click **"Make Active →"**
   - *Say:* "In 15 seconds, we've created a scenario where high-priority units grow 25%. In a spreadsheet, this would take hours of copy-paste across multiple tabs."

2. **Scenario Lab → Adjust Excluded Floors** *(0:30)*
   - In Scenario-Wide Controls, click **Excluded Floors** and select **B1-T1-F5** (one floor)
   - *Say:* "We're also taking floor 5 offline — renovation, sublease, whatever the reason. Watch what happens to the plan."

3. **Scenario Lab → Run Simulation → Results** *(1:00)*
   - Click **"Run Simulation"**
   - Point to the **4 metric cards** above the results table (Total Demand, Total Allocated, Net Gap, Units at Risk)
   - Point to the **results table** — highlight units that turned RED or AMBER
   - Point to **Scenario Impact Summary** — read out the seat gap and RTO need changes
   - *Say:* "Instantly we can see the snapshot — [X] units at risk, a net gap of [Y] seats. The results table shows every unit's status. No spreadsheet formula maintenance required."

4. **Scenario Lab → Changes vs. Baseline** *(0:30)*
   - Scroll to the **Changes vs. Baseline** section
   - Show the comparison table and bar chart
   - *Say:* "This is the before/after. With growth plus the lost floor, we're short [X] seats. Now we can make a decision: expand to another floor, sublease less, or negotiate differently — all backed by data."

5. **Scenario Lab → Download Report** *(0:30)*
   - Open the **Download Report** expander
   - Click **"Download Scenario Report (.xlsx)"**
   - *Say:* "Everything we just saw can be exported as a management report — allocation by unit, floor assignments, risk alerts — ready to share with leadership or Real Estate."

---

## Flow 3 — "How much money are we leaving on the table?" *(~3.5 minutes)*

**Goal:** Show the financial case — seats saved, floors freed, dollar savings.

**Steps:**

1. **Switch back to Baseline scenario** *(0:15)*
   - In the **Manage Scenarios** expander, select **Baseline** → **Make Active →**
   - Run Simulation again (or note results are already shown)
   - *Say:* "Back to the baseline — let's now look at what optimization reveals."

2. **Optimization tab → RTO-Based → Run** *(1:00)*
   - Go to **Optimization** tab
   - Note the **"No scenario constraints active"** caption (or scenario settings if a mandate is set)
   - Select objective: **"RTO-Based (Free Capacity)"**
   - Click **"Run Optimization"**
   - Point to the **Savings Summary**: "Policy-Based Seats (80% Rule)" vs "Attendance-Based Seats" — seats saved and floors freed
   - *Say:* "The optimizer looks at actual attendance patterns and asks: how many seats do we *actually* need? It's allocating by real demand — not the 80% rule. We've just freed [X seats] across [Y floors]."

3. **Optimization → Cost Estimation Panel** *(0:45)*
   - In the **Cost Estimation Panel**, type **10000** in the $/seat/year field
   - *Say:* "Our real estate cost is roughly $10,000 per seat per year — industry standard for premium office space."
   - Point to **Annual Cost** and **Potential Annual Savings**
   - *Say:* "That's [$X million] in annual savings — just from right-sizing against attendance data. The platform computed this in under 5 seconds. The same analysis in a spreadsheet would take weeks."

4. **Optimization → Sensitivity Analysis** *(0:45)*
   - Click **"Run Sensitivity Analysis"**
   - Show the **Lean / Balanced / Conservative** seat demand comparison
   - *Say:* "We don't always agree on assumptions. This shows the seat demand range across pessimistic, balanced, and aggressive attendance scenarios. Leadership can pick a point on the curve — the data is there to defend any choice."

5. **Optimization → What-If RTO** *(0:45)*
   - Select objective: **"What-If RTO"**
   - Drag the RTO slider from **3.5** to **4.0** days/week
   - Click **"Run Optimization"**
   - *Say:* "What if we increase the RTO mandate from 3.5 to 4 days? Seat demand goes up — we can see exactly by how much, per unit, before issuing any policy change. No surprises."

---

## Flow 4 — "How do we govern this?" *(~1.5 minutes)*

**Goal:** Show auditability and control — key for leadership trust.

**Steps:**

1. **Scenario Lab → Lock a Scenario** *(0:30)*
   - In **Manage Scenarios**, open Lock/Unlock
   - Select the **Aggressive Growth** scenario → click **"Toggle Lock"**
   - Show the **🔒** in the sidebar selector
   - *Say:* "Once leadership approves a scenario, we lock it. No one can accidentally change it. The lock is visible everywhere — in the sidebar, in the scenario list."

2. **Admin → Audit Trail** *(0:30)*
   - Go to **Admin** tab, scroll to **Audit Trail**
   - Show the log of actions: simulation runs, scenario creates, data edits
   - *Say:* "Every action in the platform is logged — who did what, when, and what changed. This is the governance layer that spreadsheets simply don't have."

3. **Closing** *(0:30)*
   - *Say:* "In 10 minutes, we've loaded data, run a baseline, modeled a growth + floor-loss scenario, identified [$X million] in potential savings through RTO optimization, and exported a management report — all without touching a spreadsheet. The question isn't whether to use data for seat planning. It's how soon we start."

---

## Demo Cheat Sheet

| Timing | Tab | Action | Key Message |
|--------|-----|--------|-------------|
| 0:00 | Admin | Load Sample Data | "Real data from HRIS + badge systems" |
| 0:15 | Scenario Lab | Run Simulation | "Baseline in one click" |
| 0:45 | Executive Dashboard | Show KPIs + alert badge → open RTO Alerts expander | "🔴/🟡/⚠️ badge = 30-second read for leadership" |
| 2:00 | Scenario Lab | Create Aggressive Growth template | "Scenario in 15 seconds" |
| 2:30 | Scenario Lab | Exclude a floor, re-run | "Floor offline — instant impact" |
| 3:00 | Scenario Lab | Show 4 metric cards + results table (RED/AMBER units) | "Snapshot: [N] units at risk, [X] seat gap" |
| 3:30 | Scenario Lab | Show Changes vs. Baseline | "Before/after, data-backed" |
| 4:00 | Scenario Lab | Download report | "Board-ready in one click" |
| 4:30 | Optimization | Note scenario settings caption → RTO-Based run | "How many seats do we actually need?" |
| 5:15 | Optimization | Cost Estimation ($10K/seat) | "[$X million] annual savings" |
| 6:00 | Optimization | Sensitivity Analysis | "Defensible under any assumption" |
| 6:45 | Optimization | What-If RTO (3.5 → 4 days) | "Policy change modeled instantly" |
| 7:30 | Scenario Lab | Lock scenario | "Approved plan is protected" |
| 8:00 | Admin | Audit Trail | "Full governance, no spreadsheets" |
| 8:30 | — | Closing | "[$X million] in 10 minutes" |

---

## Anticipated Questions & Answers

| Question | Answer |
|----------|--------|
| *"How accurate is the attendance data?"* | The platform works with whatever data you have — badge swipes, calendar data, surveys. Better data = better precision. Even with rough estimates, it outperforms the flat 80% rule. |
| *"What if a unit refuses to give up floors?"* | The optimizer supports unit-level overrides — pin Engineering to Tower 1, guarantee Sales a minimum of X seats. Every constraint is configurable at run time. |
| *"Can this integrate with our HRIS?"* | Yes — the platform accepts standard CSV/Excel exports. A direct API integration with Workday or SAP can be added. The data schema is documented. |
| *"Who maintains this?"* | Minimal maintenance — quarterly data refresh (~2 hours). No infrastructure beyond a web server. The tool is self-contained. |
| *"What's the rollout plan?"* | Three steps: (1) Data collection from Facilities + HR — 2-4 weeks. (2) Deploy to internal cloud — 1 week. (3) Train planners — 2 sessions. Total: 6-8 weeks to live. |
| *"Is the 80% rule going away?"* | No — it's the foundation. The platform validates it against real attendance and surfaces where it over- or under-allocates. Leadership keeps control over the rule; the platform makes the consequences visible. |
