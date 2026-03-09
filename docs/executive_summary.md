# Intelligent Seat Planning: Using Data & Analytics to Optimize CPG Real Estate

---

## Slide 1: Executive Summary

### The Challenge

CPG currently allocates office seats using static rules — typically a flat percentage of unit headcount (e.g., 80%). While simple, this approach creates significant inefficiencies:

- **Over-provisioning**: Some units receive more seats than their actual attendance patterns require
- **Under-utilization**: Allocated floors sit partially empty because real attendance is lower than the rule assumes
- **No visibility**: No way to compare what's allocated vs. what's actually used, or to model the impact of changes
- **Manual planning**: Scenarios (growth, floor closures, RTO policy changes) are modeled in spreadsheets — slow, error-prone, and not auditable
- **No tactical awareness**: No view of next-week seat demand spikes before they happen

### The Solution

A **data-driven seat planning platform** that combines:

1. **CPG's allocation rules** (80% global allocation) with **real attendance data** (median headcount, peak days, RTO patterns)
2. **Mathematical optimization** (Linear Programming) to find the best seat placement across buildings and floors
3. **Scenario intelligence** for instant what-if modeling with before/after comparisons
4. **Demand forecasting** for both long-range planning (6 months) and tactical short-term visibility (5–21 days)
5. **Behavioral analytics** to identify peak-day conflicts across departments and suggest RTO load balancing

### The Outcome

| Metric | Before (Spreadsheet) | After (Platform) |
|--------|---------------------|-------------------|
| Planning cycle | Weeks | Minutes |
| Allocation basis | Static rule only | Rule + attendance validation |
| Scenario modeling | Manual, one at a time | Instant, side-by-side matrix |
| Floor optimization | Not possible | LP-based, automated |
| Short-term demand visibility | None | 5–21 day forecast with capacity alerts |
| Peak day conflicts | Unknown | Auto-detected with stagger suggestions |
| Overflow floor planning | Not visible | Auto-identified: available flex floors surfaced on breach days |
| Audit trail | None | Full change log |

---

## Slide 2: How Technology, Data & Analytics Improve Seat Allocation

### Five Pillars

#### 1. Data-Driven Allocation & Validation

Instead of relying solely on the 80% rule, the platform validates every allocation against **actual attendance behavior**:

- **Median HC**: How many people typically come in each month
- **Peak HC**: Surge capacity needed on the busiest days
- **RTO Days/Week**: How many days per week each unit actually attends office

**The formula**: `RTO Need = (Median HC + Peak Buffer) × (RTO Days / 5)`

This tells you exactly how many seats each unit *actually needs* — and where the 80% rule is over-allocating or under-allocating.

#### 2. Optimization Engine

A **Linear Programming optimizer** places units across floors to:

- **Minimize floors used** — consolidate teams onto fewer floors, freeing real estate
- **Maximize team cohesion** — keep units on the same or adjacent floors (same tower > same building > cross-building)
- **Respect constraints** — floor capacity limits, excluded floors, capacity reductions

Three optimization modes:
- **Optimal Placement**: Seat everyone per the allocation rule on the fewest possible floors
- **RTO-Based**: Allocate by actual attendance patterns — typically frees 20–40% of seats
- **What-If RTO**: "If everyone came in 4 days/week instead of 3, what changes?"

Advanced runtime constraints:
- **Max floors per unit** — cap fragmentation by design
- **Pin units to a tower** — respect lease obligations or security zones
- **Minimum seats guarantee** — protect critical units under scarcity
- **Cluster-Diverse Placement** — use attendance correlation groups to ensure floors have units with offsetting peak days, reducing floor saturation risk

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

**Scenario Comparison Matrix**: Automatically evaluates up to 24 combinations of allocation %, RTO mandates, and capacity reductions — ranks them by utilization, waste, and cost efficiency — so the best scenario is identified without manual trial-and-error.

#### 4. Demand Forecasting

**Short-term tactical (5–21 days) — primary view:**
- Attendance Trends chart with short-term horizon radio (6 / 10 / 15 / 21 days) — shows HW ETS forecast with widening confidence band for the selected horizon; KPI shows "Forecast Peak" at end of horizon + MAPE accuracy badge
- Next 5 / 10 / 15 / 21 business day seat demand forecast ("How many seats will we need this week?")
- Per-unit Holt-Winters ETS models; fallback to day-of-week medians + unit slope for sparse units
- Configurable capacity risk threshold (default: >90% = alert)
- Holiday exclusion — configured dates are automatically skipped
- Per-unit daily breakdown toggle — see which teams drive demand on which days
- Color-coded bar chart: green (safe) / amber (moderate) / red (>90% capacity)
- **Peak Day Overflow Planning** — auto-surfaced when breach days exist: shows which floors have spare seats and which units have shortfalls, with a plain-English operational tip for temporary flex desk coordination

**Long-range (6-month trend) — available via "Long-Term Planning" expander:**
- **Holt-Winters Additive ETS** — triple exponential smoothing capturing level, trend (damped), and Mon–Fri weekly seasonality; automatically selected when ≥ 12 weekday observations and < 20% data gaps exist; falls back to linear regression + EMA for sparse datasets
- Forecast Summary table: 6-Month Change % (bounded ±100%), Trend Direction (↑ Growing / → Stable / ↓ Declining) — end-of-period projected values, floored at 0
- "Apply 6-Month Growth Estimate" — push data-driven growth directly into What-If scenarios
- Probabilistic demand at 90th/95th/99th percentile — quantifies potential seat savings vs. peak-based planning

**Demand Analytics Report Download:**
- Full Excel (.xlsx) + PDF download directly from the Demand Analytics tab
- 8 sheets/pages: Executive Summary, Forecast Summary, Short-Term Forecast, DOW Patterns, Capacity Breach Risk, Load Balancing Advisory, Overflow Planning (conditional), Temporal Clusters
- Every sheet includes a "Recommended Action" column with CPG-ready operational guidance

#### 5. Behavioral Day-of-Week Analytics

**DOW Heatmap**: Median in-office count by unit × weekday — identifies which days each department peaks.

**Peak Day Load Balancing Advisory** *(renamed from "RTO Load Balancing Advisory" for clarity)*:
- Automatically identifies each department's peak day
- Detects cross-unit conflicts: multiple departments peaking on the same day
- Generates stagger suggestions: "Engineering peaks on Wednesday — suggest shifting some demand to Monday (lightest company-wide day)"
- Auto-expands when overloaded days are detected; collapsed when load is balanced
- Advisory only — designed to inform management conversations, not auto-apply

**Temporal Clustering**: Groups departments by attendance correlation (≥0.7). Used for:
- Floor placement diversity (cross-cluster co-location stabilizes floor utilization)
- Identifying which units will simultaneously spike demand on the same day

**Real vs Perceived Capacity Breach** *(Advanced Insights — dual view)*:
- **📊 Statistical Risk (Historical)**: How often has actual attendance exceeded allocation? Breach probability, expected overflow days/month, seats to add — based purely on historical daily records
- **🎯 Scenario Risk (Forecast vs Allocation)**: Does the short-term forecast peak exceed allocated seats? Compares HW demand forecast against policy-assigned allocation. Columns explicitly labeled `📋 [Scenario]` (policy-derived) vs `📊 [Statistical]` (attendance-derived) to eliminate ambiguity
- **Real vs Perceived verdict per unit**: 🟠 Confirmed (both exceed) · 🔴 Real Breach (forecast only) · 🟡 Perceived Risk (historical 95th pct only) · 🟢 Safe
- **Scenario selector**: Compare against the Active Scenario OR any result from the Scenario Comparison Matrix — lets planners test whether a different What-If policy would resolve the breach before committing to it

---

### Scenario Planning vs. Optimization — How They Work Together

These are two distinct capabilities that answer two different questions. They are designed to run in sequence.

#### What-If Analysis — *"How many seats does each unit need, and where do they go?"*

The **What-If Analysis** tab combines two functions:

**Policy Simulation (Demand)**
- Set business assumptions: growth/attrition per unit, excluded floors, RTO mandate, allocation % overrides
- Run simulation → seat allocation per unit, gap analysis, risk flags

**LP Optimizer (Placement)**
- Takes simulation outputs and assigns units to specific floors in specific buildings
- Three objectives: Optimal Placement / RTO-Based / What-If RTO
- One click to accept and apply to the active scenario

**The Workflow:**

```
Step 1 — Set Unit Overrides     Step 2 — Run Policy Simulation
────────────────────────        ──────────────────────────────
Growth rates, floor exclusions  Seat allocation per unit computed
RTO mandate, alloc % overrides  Gap analysis, risk flags shown
        │
        ▼
Step 3 — Simulate & Optimize    Step 4 — Accept & Apply
────────────────────────────    ──────────────────────────
LP solver assigns units to      Optimized floor plan pushed
specific floors                 to scenario; visible across all tabs
        │
        ▼
Step 5 — Scenario Comparison Matrix (optional)
──────────────────────────────────────────────
Auto-evaluates 24 alloc/RTO/capacity combos
Ranks by efficiency; adopt best scenario in one click
```

---

### Data Required

| Data Source | Examples | Refresh Frequency |
|-------------|----------|-------------------|
| HR / HRIS | Headcount, growth projections, attrition | Quarterly |
| Badge / Access Systems | Daily in-office count by unit | Monthly export |
| Facilities | Building/tower/floor structure, seat capacity | As-needed |
| Business Units | Priority ranking, allocation % overrides | Annual |

---

## Slide 3: Benefits, Costs & ROI

### Qualitative Benefits

| Benefit | Description |
|---------|-------------|
| **Real estate cost reduction** | RTO-based optimization typically reveals 20–40% fewer seats needed vs. flat rule. Potential to free entire floors for sublease or consolidation. |
| **Proactive capacity management** | Short-term forecast with 90% threshold alerts flags overload days 1–3 weeks in advance — before catering, parking, and facility teams are caught off-guard. |
| **Better employee experience** | Cohesion scoring keeps teams on same/adjacent floors. Cluster-diverse placement prevents peak-day floor saturation. |
| **Faster planning cycles** | Scenarios that took weeks run in seconds. The Scenario Comparison Matrix evaluates 24 options simultaneously. |
| **RTO load balancing** | DOW conflict detection and stagger suggestions enable data-backed conversations with department heads about shifting peak days — flattening demand without mandate changes. |
| **Risk visibility** | Automated alerts: floor saturation, unit shortfalls, RTO non-compliance, cross-building fragmentation, 90%+ utilization days. |
| **Audit trail & governance** | Every change is logged with timestamp, user, old/new value, and rationale. Supports compliance and decision review. |

### Costs to Execute

| Item | Effort | Timeline |
|------|--------|----------|
| **Data collection** (one-time) | Gather daily attendance data from badge/HR systems, building floor plans, unit headcount | 2–4 weeks (Facilities + HR) |
| **Platform deployment** | Tool is built and ready. Deploy to cloud (Streamlit Cloud / internal hosting) | ~1 week |
| **Change management** | Train real estate planners and BU leads on the platform | 2–3 sessions |
| **Ongoing maintenance** | Quarterly data refresh (attendance, headcount). Minimal engineering. | ~2 hours/quarter |

### Illustrative ROI Calculation

| Parameter | Value |
|-----------|-------|
| Average seat cost (premium office, industry range) | $8,000 – $12,000 / year |
| Excess seats identified via RTO-based optimization (example) | 200 seats |
| **Annual direct savings** | **$1.6M – $2.4M** |
| Indirect savings (facilities overhead, energy, cleaning for freed floors) | Additional 10–15% |
| Implementation cost (one-time) | < $50K (data collection + deployment + training) |
| **Payback period** | **< 1 month** |

*Note: Actual savings depend on CPG's real estate portfolio size, current utilization rates, and lease terms. The platform quantifies exact numbers once real data is loaded.*

---

## Key Features by Tab

| Tab | Key Capabilities |
|-----|-----------------|
| 📊 **Executive Dashboard** | KPI cards (supply/demand/gap), 1-week forecast card + overflow risk callout (when >90% days detected), Key Insights strip, Planning Alerts (capacity / RTO / other), AI Executive Brief |
| 🤖 **What-If Analysis** | Unit overrides, policy simulation, LP optimizer (3 modes), cost estimation, sensitivity analysis, Scenario Comparison Matrix (24 combos, auto-ranked), report download (Excel + PDF) |
| 🏗️ **Spatial / Floor View** | Floor utilization heatmap, consolidation suggestions |
| 👥 **Unit Impact View** | Per-unit risk table, seat gap, fragmentation scores, floor assignments |
| 📈 **Demand Analytics** | Short-term trend chart (6/10/15/21-day radio, HW ETS + MAPE), probabilistic demand (90/95/99%), short-term seat demand forecast (5–21 days, per-unit HW models), **peak day overflow planning** (auto-shown on breach days), **peak day load balancing advisory** (auto-expands on overload), DOW heatmap, **Real vs Perceived Capacity Breach** (statistical + scenario risk dual-view; What-If scenario selector), temporal clustering + cluster placement advisory, 6-month forecast + Apply button (Long-Term Planning expander), **report download (Excel + PDF)** |
| 🗂️ **Floor Plan Sandbox** | Upload/edit floor layouts, 4 quick actions (move unit, remove floor, add assignment, resize), impact simulation, re-optimize, accept & push to scenario |
| ⚙️ **Admin** | Data upload (single Excel or 3-file, with step-by-step progress), base data editor, rule configuration, audit trail |

---

## 7-Minute Executive Demo Script

> **Setup before the meeting:** Launch the app (`streamlit run app.py`), open it in a browser, keep this script on a second screen. No data needed — the demo is fully self-contained.

---

### Flow 1 — "Let's see the current state" *(0:00 – 1:30)*

**Goal:** Establish the baseline and show instant executive visibility.

**Steps:**

1. **Admin → Load Sample Data** *(0:00 – 0:20)*
   - Click **"Load Sample Data"**
   - A step-by-step progress panel appears: *Generating profiles → 90-day attendance → Policy simulation → Clusters & holidays → Done ✓*
   - *Say:* "One click — 2 buildings, 4 towers, 20 floors, 8 business units, 90 days of attendance history. You can see each step completing in real time. In production this pulls from your badge system and HRIS. All tabs are now ready."

2. **Executive Dashboard** *(0:20 – 1:30)*
   - Point to **KPI cards** — supply, demand, seat gap, units with shortfall
   - Point to **1-Week Forecast card** — show next 5 days with RED/YELLOW/GREEN bars
   - *Say:* "This is something we don't have today. By Wednesday we're forecast to hit [X]% utilization — facilities, catering, parking all need to know this in advance."
   - If a red overflow callout appears below the forecast: *Say:* "The platform flags it immediately — '[N] days this week exceed 90% capacity.' And it tells us exactly where to go for overflow floor options. We'll see that in Demand Analytics in a moment."
   - Point to **Key Insights strip** — read the top 🔴 risk card and top 💡 opportunity card
   - Scroll to **Planning Alerts** — point to the 3-column alert badge, open the 🟡 RTO Alerts expander
   - *Say:* "This is the one screen leadership sees every cycle. The insights strip tells you what to act on — biggest shortfall, best consolidation opportunity, estimated savings. The alerts tell you where the fires are."

---

### Flow 2 — "What does optimization save us?" *(1:30 – 3:30)*

**Goal:** Show the financial case — seats saved, floors freed, dollar value.

**Steps:**

1. **What-If Analysis → Run Policy Simulation** *(1:30 – 2:00)*
   - Go to **What-If Analysis** tab
   - Click **"Run Policy Simulation"** (no changes — baseline assumptions)
   - *Say:* "This computes the 80% rule allocation for every unit and validates it against real attendance data. Instantly we see which units are over-provisioned and which are at risk."

2. **What-If Analysis → Simulate & Optimize (RTO-Based)** *(2:00 – 3:00)*
   - Scroll to **Optimize Floor Placement**, select **"RTO-Based (Free Capacity)"**
   - Click **"Simulate & Optimize"**
   - Point to **Savings Summary**: policy-rule seats vs. attendance-based seats, floors freed
   - *Say:* "The optimizer asks: how many seats do we *actually* need based on real attendance? Not the rule — the data. We just freed [X] seats across [Y] floors."
   - In **Cost Estimation Panel**, enter **10000** in the $/seat/year field
   - *Say:* "At $10,000 per seat per year — industry standard for premium office — that's [$X] in annual savings. Computed in under 5 seconds."

3. **Sensitivity Analysis** *(3:00 – 3:30)*
   - Click **"Run Sensitivity Analysis"**
   - Show Lean / Balanced / Conservative seat demand range
   - *Say:* "We don't always agree on assumptions. This shows the savings range across pessimistic to aggressive scenarios. Leadership can pick a point on the curve — any choice is defensible with data."

---

### Flow 3 — "What does next month look like?" *(3:30 – 5:00)*

**Goal:** Show the tactical forecasting and behavioral analytics — the features that turn planning from reactive to proactive.

**Steps:**

1. **Demand Analytics → Short-Term Seat Demand Forecast** *(3:30 – 4:00)*
   - Go to **Demand Analytics** tab
   - In **Short-Term Seat Demand Forecast**, select **21 days** on the horizon radio
   - *Say:* "This answers: how many seats will we need over the next 3 weeks? Built from historical day-of-week patterns, adjusted for trend. Red days are above 90% capacity."
   - If alert days show: *Say:* "We have [N] days flagged above 90%. That's not reactive — that's a 3-week early warning. Facilities can plan catering, parking, and meeting room allocation before it's a problem."
   - Toggle **"Per-unit breakdown"** ON briefly
   - *Say:* "We can drill into which teams are driving the demand on each day."

2. **Demand Analytics → Peak Day Overflow Planning** *(4:00 – 4:20)*
   *(This expander auto-opens if capacity risk days exist — no need to find it)*
   - Point to the **Peak Day Overflow Planning** expander (auto-expanded)
   - Point to the **Capacity risk days** column — show breach days
   - Point to the **Available overflow floors** column — show spare seats by floor
   - Point to the **Units with seat shortfall** table
   - *Say:* "The platform immediately tells us which floors have spare seats and which units need them on those peak days. This is a temporary operational arrangement — no permanent reassignment, just coordinate with Facilities for flex access on those specific days."

3. **Demand Analytics → Peak Day Load Balancing Advisory** *(4:20 – 5:00)*
   - Scroll to **Day-of-Week Attendance Patterns**
   - The **"Peak Day Load Balancing Advisory"** expander is auto-expanded if overloaded days exist
   - Point to the **company-wide load bar chart** — show the overloaded day(s) in red
   - Point to the **Peak Day per Unit** table
   - *Say:* "Wednesday is our heaviest day — [N] departments all peak on the same day. Look: Engineering, Product, and Sales are all peaking together. That's not a coincidence — they have overlapping project rhythms."
   - Point to **Stagger Suggestions** table
   - *Say:* "The platform identifies which units could shift off that day and suggests the lowest-load alternative. These are conversation starters for BU heads — voluntary shifts, no mandate needed. If even 2 of these units shift, we flatten the Wednesday spike significantly."

---

### Flow 4 — "Which scenario should we go with?" *(5:00 – 6:15)*

**Goal:** Show the Scenario Comparison Matrix — the feature that replaces manual scenario juggling.

**Steps:**

1. **What-If Analysis → Scenario Comparison Matrix** *(5:00 – 6:00)*
   - Go back to **What-If Analysis**, scroll to **Scenario Comparison Matrix**
   - Click **"Run Scenario Matrix"** (with default settings)
   - *Say:* "Instead of modeling one scenario at a time, the platform evaluates up to 24 combinations of allocation %, RTO mandates, and capacity reductions — all at once."
   - Point to the ranked results table
   - *Say:* "It ranks them by seat efficiency and waste. The top row is our best scenario — [X]% allocation, [Y] RTO days, with the lowest waste. No more spreadsheet juggling to find the optimum."
   - Click **"Adopt This Scenario →"** on the top-ranked result
   - *Say:* "One click — adopted. The entire platform updates to reflect the winning scenario."

2. **What-If Analysis → Download Report** *(6:00 – 6:15)*
   - Open the **Download Report** expander
   - Click **"Download Boardroom Report (.pdf)"**
   - *Say:* "Everything we've just seen — KPIs, allocation tables, optimization results, scenario comparison — in a 5-page boardroom PDF. Ready to email right now."

---

### Close — "How do we govern this?" *(6:15 – 7:00)*

1. **Admin → Audit Trail** *(6:15 – 6:45)*
   - Go to **Admin**, scroll to **Audit Trail**
   - Show the log of actions: simulation runs, scenario creates, data edits, optimizations
   - *Say:* "Every action is logged — who did what, when, and what changed. This is the governance layer that spreadsheets simply don't have. When leadership asks 'who approved this floor plan?', the answer is one scroll away."

2. **Closing** *(6:45 – 7:00)*
   - *Say:* "In 7 minutes we've seen: real-time seat health, a 3-week demand forecast with capacity alerts, $[X]M in identified savings, behavioral analytics that pinpoint Wednesday overload, and an automated scenario matrix that found the optimal policy. The question isn't whether to use data for seat planning — it's how soon we start."

---

## 7-Minute Demo Cheat Sheet

| Time | Tab | Action | Key Message |
|------|-----|--------|-------------|
| 0:00 | Admin | Load Sample Data (watch progress steps) | "One click — all tabs ready, 90 days of data, progress visible" |
| 0:20 | Executive Dashboard | KPI cards → 1-Week Forecast → overflow callout (if red days) → Key Insights → Planning Alerts (RTO expander) | "Forecast, overflow risk, insights, alerts — one screen" |
| 1:30 | What-If Analysis | Run Policy Simulation | "Baseline in one click — validates 80% rule vs real data" |
| 2:00 | What-If Analysis | Simulate & Optimize (RTO-Based) → Cost Estimation ($10K/seat) | "[$X M] annual savings from right-sizing" |
| 3:00 | What-If Analysis | Sensitivity Analysis (Lean/Balanced/Conservative) | "Defensible under any assumption" |
| 3:30 | Demand Analytics | Short-Term Seat Demand Forecast → 21 days → per-unit toggle | "3-week early warning before peaks hit" |
| 4:00 | Demand Analytics | Peak Day Overflow Planning (auto-expanded) → overflow floors table | "These floors absorb the overflow — no permanent moves" |
| 4:20 | Demand Analytics | Peak Day Load Balancing Advisory (auto-expanded) → load bar chart → stagger suggestions | "Wed is overloaded — here's who to shift and where" |
| 5:00 | What-If Analysis | Scenario Comparison Matrix → Run → Adopt top scenario | "24 combos evaluated; best policy identified automatically" |
| 6:00 | What-If Analysis | Download Boardroom Report (PDF) | "Board-ready in one click" |
| 6:15 | Admin | Audit Trail | "Full governance — who changed what, when" |
| 6:45 | — | Closing | "[$X M] identified, zero spreadsheets" |

---

## Anticipated Questions & Answers

| Question | Answer |
|----------|--------|
| *"How accurate is the attendance data?"* | The platform works with whatever data you have — badge swipes, calendar data, surveys. Better data = better precision. Even with rough estimates, it outperforms the flat 80% rule. |
| *"What if a unit refuses to give up floors?"* | The optimizer supports unit-level overrides — pin Engineering to Tower 1, guarantee Sales a minimum of X seats. Every constraint is configurable at run time. |
| *"Can this integrate with our HRIS?"* | Yes — the platform accepts standard CSV/Excel exports. A direct API integration with Workday or SAP can be added. The data schema is documented. |
| *"How is the short-term forecast generated?"* | It uses per-unit Holt-Winters Additive ETS models (triple exponential smoothing capturing level, trend, and Mon–Fri weekly seasonality). Each unit's HW model forecasts demand on specific upcoming business days; results are summed for the total. Units with insufficient history fall back to day-of-week medians. Configured holidays are automatically excluded. The methodology is explained in full inside the platform. |
| *"How is the long-range 6-month forecast generated?"* | Holt-Winters Additive ETS with damped trend — the same statistical model used in professional demand planning software. It learns the weekly attendance rhythm (e.g., Tuesday/Wednesday peaks) from the data and projects forward with widening confidence bands. MAPE (Mean Absolute Percentage Error) is shown as the accuracy indicator. Falls back to linear regression for sparse datasets. |
| *"What are the 'stagger suggestions' based on?"* | Each unit's historical peak day is identified from attendance data. The platform detects which days carry 15%+ above average load, then recommends the lowest-load alternative day for each conflicting unit. These are advisory — no auto-changes. |
| *"What happens when demand exceeds our floor capacity on a specific day?"* | The Peak Day Overflow Planning panel automatically surfaces this when the short-term forecast shows >90% capacity days. It identifies which floors have unallocated spare seats and which units have seat shortfalls — giving Facilities a specific, actionable plan for temporary flex access on those days. No permanent reassignment is needed. |
| *"How do we know if a capacity breach is real or just statistical noise?"* | The Demand Analytics tab has a "Real vs Perceived Capacity Breach" view with two sub-tabs. The Statistical Risk tab shows how often historical attendance exceeded allocation (frequency-based). The Scenario Risk tab compares the short-term forecast peak against allocated seats — columns are explicitly labeled [Scenario] (policy-driven) vs [Statistical] (data-driven) to remove ambiguity. The verdict per unit: Confirmed Breach / Real Breach / Perceived Risk / Safe. Planners can also swap the allocation source to any Scenario Comparison Matrix result to test whether a different What-If policy would resolve the breach. |
| *"Who maintains this?"* | Minimal maintenance — quarterly data refresh (~2 hours). No infrastructure beyond a web server. The tool is self-contained. |
| *"What's the rollout plan?"* | Three steps: (1) Data collection from Facilities + HR — 2–4 weeks. (2) Deploy to internal cloud — 1 week. (3) Train planners — 2 sessions. Total: 6–8 weeks to live. |
| *"Is the 80% rule going away?"* | No — it's the foundation. The platform validates it against real attendance and surfaces where it over- or under-allocates. Leadership keeps control over the rule; the platform makes the consequences visible. |

---

## Summary: Why This Matters

| Without the Platform | With the Platform |
|---------------------|-------------------|
| "We think 80% is right" | "Data shows we need 62% for Sales, 78% for Engineering" |
| "We might have extra floors" | "We can free floors 5, 8, and 12 — saving $1.8M/year" |
| "What if RTO changes?" | "Here's the exact impact on every unit and floor" |
| "Wednesday felt busy" | "Wednesday is 94% capacity — flagged 3 weeks in advance" |
| "We need more seats on Friday — where do we put people?" | "Floor X has 42 spare seats; units A and B are in shortfall — direct them there" |
| "Why are teams scattered?" | "Cluster-diverse placement keeps peak-day floors balanced" |
| "Trust the spreadsheet" | "Full audit trail, scenario comparison matrix, risk alerts" |

**The platform turns seat planning from a cost center exercise into a strategic real estate optimization capability.**

---

## One-Pager: Executive Overview

### 1. Idea Summary
CPG offices are over-allocated using static rules that ignore actual attendance. This platform uses real badge/HR data and mathematical optimization to right-size seat allocations, consolidate floors, and quantify savings — replacing spreadsheet planning with data-driven decisions in minutes.

### 2. Business Context
| Problem | Impact |
|---------|--------|
| Flat 80% rule allocates seats regardless of actual attendance | Floors sit 30–50% empty on average days |
| No way to model RTO policy changes, growth, or floor closures | Reactive planning; surprises at lease renewal |
| Manual spreadsheet process, no audit trail | Decisions lack transparency and are hard to defend |
| Teams scattered across floors with no cohesion logic | Productivity loss; unnecessary cross-floor commute |
| No visibility into next-week demand spikes | Facilities, catering, and parking are always reactive |
| Multiple departments peak on the same day | Preventable floor saturation from uncoordinated RTO patterns |

### 3. Approach, Methodology & Implementation
- **Data inputs**: Headcount (HR/HRIS), daily attendance (badge systems), building floor plans (Facilities) — refreshed quarterly
- **Allocation engine**: Flat % rule (e.g., 80%) adjusted for growth/attrition; validated against RTO Need formula `(Median HC + Peak Buffer) × (RTO Days / 5)`
- **LP Optimizer**: Minimizes floors used + maximizes team cohesion; supports 3 objectives with runtime constraints (floor caps, tower pinning, demand guarantees, cluster diversity)
- **Demand Forecasting**: Holt-Winters Additive ETS (trend + seasonality + damped growth) for 6-month trend with MAPE accuracy metric; per-unit HW models for 5–21 day tactical forecast with capacity risk alerting; full Excel + PDF report download
- **Scenario Comparison Matrix**: Automated evaluation of up to 24 alloc/RTO/capacity combinations; auto-ranked by efficiency
- **Platform**: Web-based tool (Streamlit), deployable on internal cloud or Streamlit Cloud; no installation required
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
| Planning takes weeks | Scenarios run in seconds; Comparison Matrix evaluates 24 options simultaneously |
| No audit trail | Full change log: who changed what, when, and why |
| "We think we need X seats" | "Data shows we need X seats — here's the cost if we're wrong" |
| No advance warning of peak days | 5–21 day forecast with 90% capacity threshold alerts |
| Departments peak on same days | Behavioral analytics + stagger suggestions to flatten demand |
