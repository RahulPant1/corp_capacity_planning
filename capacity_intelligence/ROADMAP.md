# Capacity Intelligence — Data Model Redesign Roadmap

> Status: IMPLEMENTATION COMPLETE — all files updated and end-to-end tested
> Last updated: 2026-04-21

---

## Confirmed 4-Dataset Model

### Dataset 1 — Floor Capacity *(static, Facilities-owned)*
Physical seat inventory per floor. Changes rarely.

| Column | Type | Notes |
|---|---|---|
| `City` | string | e.g. Bangalore |
| `Building Name` | string | e.g. Prestige Tech Park |
| `Floor` | string/integer | e.g. 3 or "Floor 3" |
| `Total Capacity` | integer | Total physical seats on that floor |

**Natural join key:** `(City, Building Name, Floor)`

---

### Dataset 2 — Seat Allocation *(operational, CPG/Workplace-owned)*
Who sits where. Multiple LOBs can share a floor. Changes quarterly.

| Column | Type | Notes |
|---|---|---|
| `LOB` | string | e.g. Engineering |
| `LOB Leader Name` | string | e.g. Priya S. |
| `City` | string | |
| `Building Name` | string | |
| `Floor` | string/integer | |
| `Allocated Seats` | integer | Seats owned by this LOB on this floor |

A floor can have multiple rows (multiple LOBs sharing it).
**Natural join key:** `(City, Building Name, Floor)` → links to Floor Capacity and Predictions

---

### Dataset 3 — Total Headcount *(HR snapshot)*
LOB-level headcount. Not per-floor — used to compute seat gap vs allocation.

| Column | Type | Notes |
|---|---|---|
| `LOB` | string | |
| `Leader` | string | |
| `Headcount` | integer | Total HC for this LOB across all locations |

**Join key:** `LOB` → links to Seat Allocation for gap analysis

---

### Dataset 4 — 60-Day Prediction *(Model Output, time-series)*
Daily predicted employee count at floor × LOB level. Core analytics driver.

| Column | Type | Notes |
|---|---|---|
| `Date` | date | e.g. 2026-05-01 |
| `Day` | string | Day-of-week name (Mon, Tue…) |
| `City` | string | |
| `Building` | string | Match to "Building Name" in other datasets |
| `Floor` | string/integer | |
| `LOB` | string | Line of Business |
| `Leader` | string | LOB Leader name |
| `Holiday Flag` | boolean/integer | Public holiday |
| `Optional Holiday Flag` | boolean/integer | Org-optional holiday |
| `Optional Holiday Name` | string | Name of optional holiday if flagged |
| `US Holiday Flag` | boolean/integer | US-specific holiday marker |
| `Employee Count Predicted` | integer | Predicted footfall for this LOB on this floor on this date |

**Granularity: `(Date × City × Building × Floor × LOB)` — floor × LOB level**
**Natural join key:** `(City, Building, Floor, LOB)` → links to Floor Capacity and Seat Allocation

---

## Key Design Decisions — Confirmed

| # | Decision | Detail |
|---|---|---|
| 1 | Prediction granularity | **Floor × LOB** — confirmed, LOB + Leader columns present in DS4 |
| 2 | Seat Allocation | **Snapshot** — one active version, multiple rows per floor (one per LOB) |
| 3 | Seat gap (LOB level) | `Allocated Seats − Headcount` per LOB (from DS2 + DS3 join on LOB) |
| 4 | Utilization (floor level) | `Employee Count Predicted / Total Capacity` (from DS4 + DS1 join on floor key) |
| 5 | Over-allocation check | `SUM(Allocated Seats per floor) vs Total Capacity` — from DS2 + DS1 |
| 6 | Join key format | Use natural text keys `(City, Building, Floor)` — no synthetic IDs needed |

---

## Join Logic

```
Floor Capacity + Seat Allocation  (on City + Building Name + Floor)
    → Is the floor over-allocated? (sum of allocated > total capacity)
    → Which LOBs share each floor?

Seat Allocation + Total Headcount  (on LOB)
    → Seat gap per LOB = Allocated Seats − Headcount
    → Negative gap = LOB needs more space than it has

60-Day Prediction + Floor Capacity  (on City + Building + Floor)
    → utilization_pct = Employee Count Predicted / Total Capacity
    → Peak day detection, breach risk

60-Day Prediction + Seat Allocation  (on City + Building + Floor + LOB)
    → seat gap over time = Allocated Seats − Employee Count Predicted (per LOB per floor)
    → LOB-level overflow risk with full time-series

---

## Session State Keys

| Key | Content |
|---|---|
| `ci_floor_capacity_df` | Dataset 1 — Floor Capacity |
| `ci_seat_allocation_df` | Dataset 2 — Seat Allocation |
| `ci_headcount_df` | Dataset 3 — Total Headcount |
| `ci_prediction_df` | Dataset 4 — 60-Day Prediction (raw upload) |
| `ci_daily_df` | Joined working DataFrame (Prediction + Floor Capacity + Allocation) |

---

## Analytics Enabled by This Model

| Metric | Datasets Used | Granularity |
|---|---|---|
| Floor utilization over 60 days | DS4 + DS1 | Date × Floor |
| Peak day / breach risk | DS4 + DS1 | Floor |
| Floor over-allocation (static) | DS2 + DS1 | Floor |
| LOB seat gap (HC vs allocation) | DS2 + DS3 | LOB |
| Holiday impact on footfall | DS4 (holiday flags) | Date × Floor |
| LOB predicted footfall over time | DS4 | Date × LOB × Floor (direct) |
| LOB seat gap over time | DS4 + DS2 | Date × LOB × Floor |

---

## Scenario Planner — Confirmed Design

### Mode A — Event Impact
Applies multiplier adjustments on top of `Employee Count Predicted` for rows within the event window.
Custom multipliers (Townhall, Weather Alert, etc.) apply as overrides on the prediction.

### Mode B — RTO Mandate & Seat Planning
Uses **Total Headcount (DS3) as the baseline**, not historical footfall scaling.

```
Expected daily demand (per LOB) = LOB Headcount × RTO mandate %

Seats needed (per LOB)          = Expected daily demand / Target utilization %

Seat gap (per LOB)              = Allocated Seats (DS2) − Seats needed
    Positive = surplus  |  Negative = deficit
```

Planner sets:
- **RTO mandate %** — what % of LOB HC is expected in office (e.g. 60%)
- **Target utilization %** — planning buffer (e.g. 80% → builds in 20% headroom)

Replaces the old `new_rto_days / baseline_rto_days` footfall scaling approach.

---

## Decisions Locked

| Decision | Detail |
|---|---|
| Building name join key | Use `Building Name` across all 4 datasets; normalize on load (strip/lowercase) if minor differences |
| Long-Term View | **Disabled** — 60-day max prediction horizon makes 6/12-month views invalid (`tab_long_term.py` shows placeholder) |
| Scenario Planner Mode B | HC × RTO% demand baseline; seat gap vs DS2 allocation |

---

## Files Changed (Implementation Complete)

| File | Change |
|---|---|
| `data/ci_sample_data.py` | ✅ Done — 4 datasets, join helper, buildings_meta |
| `tabs/tab_admin.py` | ✅ Done — 4-step upload UI, sample load, data preview |
| `engine/capacity_forecast.py` | ✅ Done — new column schema, floor/LOB functions, Mode B engine |
| `tabs/tab_short_term.py` | ✅ Done — floor util table, LOB gap table, holiday callout, building risk drilldown |
| `tabs/tab_long_term.py` | ✅ Done — disabled with placeholder message |
| `tabs/tab_scenario_planner.py` | ✅ Done — Mode A event adjustments · Mode B HC × RTO% seat plan |
| `tabs/tab_help.py` | ✅ Done — rewritten for 4-dataset model |
| `engine/scenario_report.py` | ✅ Done — updated to new column names |

---

## Open Questions

All questions resolved. Schema confirmed — ready for implementation.
