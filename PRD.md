Product Requirements Document (PRD)
Seat Planning & Scenario Intelligence Platform (Updated)
1. Product Overview
1.1 Purpose
The Seat Planning & Scenario Intelligence Platform is an internal decision-support application that enables data-driven seat allocation, scenario planning, and optimization for Companies & Properties Group (CPG) and Business Unit Leaders.
The platform replaces static, one-size-fits-all allocation ratios with attendance-aware, behavior-aware, and growth-aware seat planning, while maintaining transparency and governance.
2. Core Planning Philosophy (IMPORTANT)
Seat allocation is treated as a function of real demand, not just headcount.
Demand is inferred using:

Monthly median in-office strength
Monthly peak in-office strength
Average return-to-office (RTO) attendance
Attrition and growth forecasts
Stability and volatility of attendance
The system recommends allocations; humans approve them.
3. Input Data Requirements (Expanded)
3.1 Building & Infrastructure Data (CPG-Owned)
(unchanged)
3.2 Unit Headcount & Forecast Data (Expanded)
FieldDescriptionUnit NameBusiness / functionCurrent Total HCCurrent total headcountMonthly Median HCMedian in-office employee count per monthMonthly Max HCPeak in-office employee count per monthHC Growth Forecast (%)Expected growth over planning horizonAttrition Forecast (%)Expected attrition over planning horizonNet HC ChangeDerived from growth – attrition
Purpose

Distinguishes theoretical HC from actual seat demand
Supports proactive planning instead of reactive escalation
3.3 Attendance & RTO Behavior Data (Expanded)
FieldDescriptionAvg RTO Days / WeekAverage days employees attend officeAttendance StabilityVariance in attendance month-to-monthPeak SynchronizationWhether peaks align with other units
Purpose

Drives intelligent allocation percentage recommendations
Identifies units that need buffers vs those that do not
4. Intelligent Seat Allocation Logic (NEW CORE FEATURE)
4.1 Allocation Percentage Justification Engine
Instead of static ratios, the system derives a recommended allocation percentage using:

Monthly median in-office HC (baseline demand)
Monthly max in-office HC (upper bound)
Avg RTO attendance (seat reuse potential)
Attendance stability (buffer sizing)
Growth & attrition forecast (future demand)
Outcome

System-generated Recommended Allocation %
Explanation of why the % was suggested
Manual override capability for CPG
4.2 Individual Unit Allocation Adjustment
The platform allows explicit modification of unit allocation percentages based on:

High attrition forecast → lower allocation %
Aggressive growth forecast → higher allocation %
Volatile attendance → buffer increase
Stable attendance → buffer reduction
Key principle

Allocation % is not fixed — it is scenario- and behavior-dependent.
5. Spatial Allocation & Floor Adjacency Rules (NEW)
5.1 Floor Cohesion & Proximity Optimization
The system prioritizes seat placement using the following hierarchy:

Same floor (preferred)
Adjacent floors (acceptable)
Same tower (fallback)
Cross-tower (last resort)
This applies to:

Baseline allocation
Scenario simulations
Optimization runs
5.2 Fragmentation Minimization
The system tracks:

Number of floors occupied per unit
Average seats per floor per unit
It actively:

Flags high fragmentation
Suggests consolidation opportunities
Quantifies operational pain of fragmentation
6. Scenario Planning Capabilities (Expanded)
6.1 Scenario Dimensions
Each scenario can independently modify:

HC growth / attrition assumptions
Avg RTO attendance
Median and peak HC assumptions
Allocation percentage logic
Available floors / seats
6.2 Scenario Types (Examples)
Baseline: Current state
Growth-Heavy Unit Scenario: One unit grows, others shrink
Hybrid Efficiency Scenario: Reduced RTO, higher reuse
Attrition-Driven Release Scenario: Seat release due to shrinkage
Floor Consolidation Scenario: Fewer floors, same demand
6.3 Scenario Outputs
For each scenario, the system shows:

Capacity gap
Unit-level shortages / surpluses
Floors saturated vs underutilized
Change in allocation percentages
Consolidation or expansion recommendations
7. Rule-Based Auto Allocation (Non-AI)
7.1 Growth vs Shrink Redistribution Rules
When total demand changes:

Growing units are allocated first (within policy bounds)
Shrinking units contribute capacity back
Scarcity is distributed proportionally and transparently
7.2 Attendance-Aware Seat Scaling
Examples:

High median, low max → lean allocation
High max, volatile attendance → buffer required
Low avg RTO → reduced permanent seats
8. Optimization Capabilities (LP-Based)
8.1 Optimization Objectives
The system can optimize for:

Minimum seat shortfall
Maximum floor cohesion
Minimum number of floors used
Fair allocation across units
8.2 Constraints (Expanded)
Floor capacity
Unit min/max allocation %
Growth and attrition projections
Floor adjacency preferences
Planning horizon locks
9. Unit-Level Capabilities (Expanded)
9.1 Unit View
Each unit sees:

Median vs peak demand
Allocated seats vs effective demand
Recommended allocation %
Fragmentation score
Forecast-based risk
9.2 Unit Interaction
Units can:

Validate attendance assumptions
Flag upcoming growth/attrition changes
Accept or challenge recommended allocations
Propose seat releases or requests
10. Governance & Transparency
10.1 Explainability
For every allocation or recommendation, the system explains:

What inputs were used
Which rules were applied
Why the outcome changed
10.2 Control & Overrides
CPG can override any recommendation
Overrides are logged with rationale
Baseline plans can be locked
11. Outputs & Decision Artifacts
Executive dashboards
Scenario comparison summaries
Unit-specific allocation sheets
Floor consolidation reports
Exportable planning packs
12. What This Product Is (Clear Positioning)
This platform is:

A behavior-aware, scenario-driven seat planning and optimization system

— not a static seat calculator.
It enables proactive, fair, and explainable decisions at scale.



Technical Implementation & UI Architecture

(Appendix to PRD)

A. Application Architecture Overview

The application shall be implemented as a Python-based interactive planning tool with a lightweight web interface.

Architecture Layers

Data Ingestion Layer

Accepts structured baseline inputs (building, unit, attendance)

Supports file upload (Excel / CSV)

Planning & Intelligence Layer

Rule-based allocation logic

Scenario simulation engine

Optimization engine (LP-based)

Presentation Layer

Interactive dashboards

Scenario controls

Visualization of spatial and unit-level impacts

The architecture must support recalculation on demand and scenario isolation.

B. UI Navigation & Hierarchy

The UI shall be organized to reflect the planning workflow, not just data visualization.

Global Controls (Sidebar)

The sidebar establishes the planning context and shall include:

Scenario selector (Baseline, Growth, Custom)

Planning horizon selector (e.g., 3 or 6 months)

Global assumptions (read-only or editable based on role)

Mode selector (View / Simulate / Optimize)

Sidebar changes shall not auto-apply without explicit user action.

C. Main Application Tabs (Intent-Based Design)
Tab 1: Executive Dashboard

Purpose: High-level planning health and feasibility.

Features:

Capacity vs demand summary

Overall seat gap

Count of impacted units

Floors at risk (saturated / underutilized)

System-generated planning alerts

This tab is read-only and optimized for leadership review.

Tab 2: Unit Impact View

Purpose: Transparency and accountability at unit level.

Features:

Unit-level seat demand vs allocation

Attendance-adjusted demand

Recommended allocation percentages

Fragmentation indicators

Unit-specific risks and gaps

Supports filtering and sorting to identify priority units.

Tab 3: Spatial / Floor View

Purpose: Operational and physical seat utilization analysis.

Features:

Tower and floor utilization views

Units per floor

Fragmentation visualization

Suggested consolidation opportunities

Identification of surplus capacity locations

This view supports CPG operational decision-making.

Tab 4: Scenario Lab

Purpose: Controlled experimentation with planning assumptions.

Features:

Unit-level overrides:

HC growth / attrition

Attendance assumptions

Allocation percentage overrides

Scenario-wide controls:

RTO mandate changes

Capacity availability changes

Explicit action triggers:

Run Simulation

Apply Rules

Reset Scenario

All changes remain isolated to the active scenario until approved.

Tab 5: Optimization & Recommendations

Purpose: Generate best-fit allocations under constraints.


Features:

Optimization objective selection

Constraint visibility

Before/after comparison of allocations

Floor consolidation suggestions

Impact summary (units helped / impacted)

Optimization results require explicit acceptance to be applied.

Tab 6: Admin & Governance

Purpose: Control, configuration, and auditability.

Features:

Data upload and refresh

Rule-set configuration

Allocation policy bounds

Scenario locking and approval

Change history and audit trail

This tab supports role-based access control.

D. Scenario Management & Lifecycle

Each scenario shall:

Be independently parameterized

Maintain its own assumptions and outputs

Support comparison with other scenarios

Be lockable once approved

The system shall prevent accidental overwriting of approved scenarios.

E. Rule-Based Allocation Engine (Non-AI)

The system shall implement deterministic, explainable rules to:

Suggest allocation percentages

Adjust for attendance behavior

Redistribute seats during scarcity

Flag inefficiencies and consolidation opportunities

All rule applications must be transparent and traceable.

F. Optimization Engine Integration

The system shall support linear programming–based optimization with:

Configurable objectives

Policy and capacity constraints

Floor adjacency preferences

Fairness and fragmentation considerations

Optimization must be optional and never automatically enforced.

G. Performance & Usability Considerations

Scenario recalculation must be responsive for interactive use

UI must avoid auto-recalculation on every control change

All critical actions require explicit user confirmation

Visual clarity prioritized over visual complexity



Unit-Level Forecast Adjustability

The application shall allow authorized users (e.g., CPG) to modify unit-level planning assumptions after baseline upload through scenario-specific overrides. These include:

Headcount growth %

Attrition %

Allocation percentage

Attendance assumptions

Such modifications:

Shall not alter baseline uploaded data

Shall be stored at the scenario level

Shall be reversible

Shall be traceable via change logs

🎯 Practical UX Implementation

In your Scenario Lab tab:

You’ll have a table like:

Unit	Baseline Growth %	Scenario Growth %	Baseline Alloc %	Scenario Alloc %

Editable fields = Scenario columns only.



📥 Input Data Contracts & Upload Requirements

(Appendix / Add-on to PRD)

This section defines the explicit data inputs required by the application.
All planning, scenario simulation, and optimization capabilities operate only on uploaded or configured data.

1. Input Mechanism

The application shall support file-based data ingestion as the primary input mechanism.

Supported formats:

Excel (.xlsx)

CSV (.csv)

Upload is performed via the Admin / Governance section

Uploaded data is validated before being used in planning

Each upload is treated as a planning baseline snapshot.

2. Required Input Files (Minimum Set)
2.1 Building & Floor Master (Mandatory)

Purpose
Defines physical seat supply and constraints.

Required Fields

Building ID / Name

Tower ID

Floor Number

Total Seats

Granularity

One row per floor

Used By

Capacity validation

Floor-level allocation

Optimization constraints

2.2 Unit Headcount & Forecast File (Mandatory)

Purpose
Defines demand drivers and future planning assumptions.

Required Fields

Unit Name

Current Total Headcount

HC Growth Forecast (%)

Attrition Forecast (%)

Optional (Strongly Recommended)

Business Priority / Criticality

Used By

Demand estimation

Scenario simulations

Scarcity redistribution logic

2.3 Attendance & RTO Behavior File (Mandatory for Intelligence)

Purpose
Enables behavior-aware seat allocation.

Required Fields

Unit Name

Monthly Median In-Office Strength

Monthly Max In-Office Strength

Average RTO Days per Week

Optional

Attendance variance / stability indicator

Used By

Allocation percentage justification

Buffer sizing

Ratio recommendations

Scenario realism