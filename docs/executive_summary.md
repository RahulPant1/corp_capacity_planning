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

- **KPI cards**: Total supply, demand, seat gap, units with shortfall
- **Capacity vs. Demand chart**: By tower, at a glance
- **Utilization donut**: Overall seat utilization percentage
- **Grouped alerts**:
  - Capacity alerts (floor saturation, unit shortfalls)
  - RTO alerts (under-utilized seats, under-allocated units)
  - Other (fragmentation, cross-building spread)

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
