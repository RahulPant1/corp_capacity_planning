"""Help tab — reference guide for the 4-dataset model, calculations, and thresholds."""


def render() -> None:
    import streamlit as st

    st.markdown("### 📖 How This App Works")
    st.caption("Reference guide for all data inputs, calculations, formulas, and thresholds used across the app.")

    # ── Getting Started ────────────────────────────────────────────────────────
    with st.expander("0 · Getting Started — How to Load Data", expanded=True):
        st.markdown("""
The app requires **four datasets** to be active before any tab shows data.
You can load them in two ways — both are available in the **⚙️ Admin** tab.

---

#### Path A — Sample Data (fastest, one click)

Go to **⚙️ Admin → Use Sample Data → Load Sample Data**.

The built-in dataset covers 12 buildings across 4 cities (Bangalore, Hyderabad, Chennai, Manila),
7 LOBs, 2–3 floors per building, and 60 days of predicted attendance with holiday flags.
All tabs activate instantly — use this for demos or to explore the tool before loading your own data.

---

#### Path B — Upload Your Own Data (4 files, in order)

Go to **⚙️ Admin → Upload Your Data**. Each dataset has an expander with a **Download template** button.

| Step | Dataset | File format | What to prepare |
|------|---------|-------------|-----------------|
| 1 | Floor Capacity | CSV or Excel | One row per floor — City, Building Name, Floor, Total Capacity |
| 2 | Seat Allocation | CSV or Excel | One row per LOB × floor assignment — who sits where |
| 3 | Total Headcount | CSV or Excel | One row per LOB — total HC across all locations |
| 4 | 60-Day Prediction | CSV or Excel | Daily model output at floor × LOB granularity |

Once all four files pass validation the datasets are **joined automatically** — no button press needed.

---

#### What each dataset unlocks

| Dataset missing | Features that will not work |
|---|---|
| Any dataset | All tabs show "no data loaded" — all four are required together |
| **Dataset 4 — 60-Day Prediction** | Short-Term View (30/60-day forecasts), Executive Dashboard charts, utilization heatmaps, Scenario Planner impact simulation — nothing time-series based works |
| **Dataset 3 — Total Headcount** | Scenario Planner Mode B (RTO mandate & seat planning), static seat gap vs headcount |
| **Dataset 2 — Seat Allocation** | Seat gap per LOB, over-allocation checks, LOB breakdown in floor cards |
| **Dataset 1 — Floor Capacity** | Utilization % calculation (requires total capacity per floor) |

> **Key dependency:** The **60-day prediction file (Dataset 4) is the engine of the entire app.**
> Without it the 30-day and 60-day horizon views, all utilization KPIs, and the dashboard
> attendance charts are unavailable — even if the other three datasets are loaded.

---

#### Switching datasets

Use **Clear all data** in the Admin status banner to reset. Individual datasets can be replaced
via the **Replace** button inside each dataset expander (Upload mode only).
""")

    with st.expander("1 · Data Model — Four Inputs", expanded=True):
        st.markdown("""
This app requires **four datasets**, uploaded separately in the Admin tab.

---

**Dataset 1 — Floor Capacity** *(static, Facilities-owned)*

Physical seat inventory. Changes rarely.

| Column | Type | Description |
|--------|------|-------------|
| `City` | string | City the building is in |
| `Building Name` | string | Human-readable building name |
| `Floor` | string / integer | Floor identifier (e.g. 3 or "Floor 3") |
| `Total Capacity` | integer | Total physical seats on that floor |

---

**Dataset 2 — Seat Allocation** *(operational, CPG/Workplace-owned)*

Who sits where. Multiple LOBs can share the same floor.

| Column | Type | Description |
|--------|------|-------------|
| `LOB` | string | Line of Business |
| `LOB Leader Name` | string | LOB leader responsible for that allocation |
| `City` | string | |
| `Building Name` | string | |
| `Floor` | string / integer | |
| `Allocated Seats` | integer | Seats owned by this LOB on this floor |

A floor will have **multiple rows** when more than one LOB shares it.

---

**Dataset 3 — Total Headcount** *(HR snapshot)*

LOB-level total headcount — not per-floor.

| Column | Type | Description |
|--------|------|-------------|
| `LOB` | string | Line of Business |
| `Leader` | string | LOB leader name |
| `Headcount` | integer | Total HC for this LOB across all locations |

---

**Dataset 4 — 60-Day Prediction** *(model output, time-series)*

Daily predicted attendance at **floor × LOB** granularity. This drives all charts and KPIs.

| Column | Type | Description |
|--------|------|-------------|
| `Date` | date | Calendar date |
| `Day` | string | Day-of-week name (Mon, Tue …) |
| `City` | string | |
| `Building` | string | Must match `Building Name` in DS1/DS2 |
| `Floor` | string / integer | Must match `Floor` in DS1/DS2 |
| `LOB` | string | Must match `LOB` in DS2/DS3 |
| `Leader` | string | LOB leader name |
| `Holiday Flag` | 0 / 1 | Public / national holiday |
| `Optional Holiday Flag` | 0 / 1 | Org-optional holiday |
| `Optional Holiday Name` | string | Name of the optional holiday (if flagged) |
| `US Holiday Flag` | 0 / 1 | US-specific holiday marker |
| `Employee Count Predicted` | integer | Predicted attendance for this LOB × floor × date |

**Granularity:** `Date × City × Building × Floor × LOB`

---

**Join logic (auto-applied on load):**

```
DS4 + DS1  (on City + Building + Floor)
    → utilization_pct = Employee Count Predicted / Total Capacity

DS4 + DS2  (on City + Building + Floor + LOB)
    → seat gap = Allocated Seats − Employee Count Predicted

DS2 + DS1  (on City + Building + Floor)
    → over-allocation check: SUM(Allocated Seats per floor) vs Total Capacity

DS2 + DS3  (on LOB)
    → static seat gap: Allocated Seats − Headcount (snapshot, not time-series)
```
""")

    with st.expander("2 · Short-Term View — What It Shows", expanded=True):
        st.markdown("""
> **Requires Dataset 4 (60-Day Prediction).** Without it this tab shows "no data loaded"
> regardless of whether the other three datasets are present.

The Short-Term View slices the prediction dataset to the selected planning window.

| Horizon option | Date range |
|---|---|
| 30 days | today → today + 30 |
| 60 days | today → today + 60 |

**All KPIs and charts use weekdays only (Mon–Fri).** Weekends are excluded from every calculation.

**4 KPI cards (top of tab):**

| Card | What it shows |
|---|---|
| Peak Predicted | Highest single-day attendance across the portfolio in the window |
| Avg Daily Predicted | Mean daily attendance across all weekdays |
| Buildings >90% Peak | Count of buildings where any weekday exceeds 90% of capacity |
| Buildings <60% Avg | Count of buildings averaging below 60% utilization |

**Three detail expanders:**

| Expander | Content |
|---|---|
| 🏢 Building Risk Details | Per-building risk tier (🔴/🟡/🔵/🟢), avg util %, peak util %, peak predicted seats |
| 🏗️ Floor Utilization | Per-floor avg util %, peak util %, risk tier |
| 👥 LOB Seat Gap (Allocation vs Headcount) | Static gap: `Allocated Seats − Total Headcount` per LOB — **not time-series** |

> **LOB seat gap is a static snapshot**, not a per-day forecast. It answers: does each LOB have enough
> allocated seats for its total headcount on paper? Negative = the LOB's headcount exceeds its seat allocation.

**Key metrics computed:**

| Metric | Formula |
|---|---|
| Floor utilization % | `Employee Count Predicted / Total Capacity` per floor per day |
| LOB seat gap (static) | `Allocated Seats − Total Headcount` per LOB (snapshot, not time-series) |
| Peak day | Day with highest total predicted attendance across selected scope |
| Holiday impact | Days with any holiday flag set are shown in an info callout |

**Additional charts (below insights):**

| Chart | What it shows |
|---|---|
| Daily forecast line | Predicted daily attendance across the horizon with a capacity reference line |
| Day-of-week bar | Average attendance by weekday (Mon–Fri) — identifies low-attendance days |
| Capacity calendar | Calendar heat-map showing daily utilization colour-coded by risk tier |
""")

    with st.expander("3 · Long-Term View", expanded=False):
        st.markdown("""
**Not available in this version.**

The prediction file covers a maximum 60-day horizon. Long-term (6–12 month) views will be enabled
once a longer-range model output is available.
""")

    with st.expander("4 · Scenario Planner", expanded=True):
        st.markdown("""
> **Mode A** requires Dataset 4 (60-Day Prediction) for impact simulation.
> **Mode B** requires Dataset 3 (Total Headcount) and Dataset 2 (Seat Allocation) for seat gap calculations.

#### Mode A — Event Impact

Applies an adjustment multiplier to predicted attendance rows that fall **within the event date window**
and match the selected scope (portfolio-wide, specific buildings, or specific LOBs).

```
adjusted_footfall = Employee Count Predicted × combined_multiplier

combined_multiplier = event_mult_1 × event_mult_2 × … × (1 + custom_pct / 100)
```

**Default event multipliers** (configurable in ⚙️ Admin → Scenario Adjustment Configuration):

| Event | Default Multiplier | Effect |
|-------|-------------------|--------|
| Townhall | ×1.20 | +20% attendance |
| Leadership Visit | ×1.15 | +15% attendance |
| Weather Alert | ×0.70 | −30% attendance |
| Traffic / Local Disruption | ×0.80 | −20% attendance |
| Mandatory Holiday | ×0.10 | −90% attendance |
| Optional Holiday | ×0.60 | −40% attendance |
| US Holiday | ×0.75 | −25% attendance |

Multiple events combine multiplicatively: e.g. Townhall + Optional Holiday = 1.20 × 0.60 = ×0.72 (net −28%).

---

#### Mode B — RTO & Seat Planning

The planner sets two levers and the tool computes how many seats each LOB needs.
Calculation uses **Total Headcount** (Dataset 3) — not actual attendance — for a consistent planning baseline.

```
RTO fraction                    = RTO days per week / 5

Expected daily demand (per LOB) = Total Headcount × RTO fraction

Seats needed (per LOB)          = Expected daily demand / Target utilization %

Seat gap (per LOB)              = Current Allocated Seats − Seats needed
    Positive gap = surplus seats
    Negative gap = seats deficit — need more allocation or fewer RTO days
```

**Example:** Engineering has 200 HC. RTO = 3 days/week → fraction = 3/5 = 60% → expects 120 people/day.
Target utilization = 80% → needs `120 / 0.80 = 150` seats.
Currently allocated 130 seats → gap = **−20** (deficit).

**Levers:**

| Control | Range | What it means |
|---|---|---|
| RTO mandate | 1–5 days/week | How many days per week each LOB is expected in office |
| Target utilization % | 50–95% | Planning buffer — lower % = more buffer seats |

Headcount baseline comes from **Dataset 3 (Total Headcount)**. Allocated seats come from **Dataset 2 (Seat Allocation)**.
""")

    with st.expander("5 · Risk Thresholds & Utilization", expanded=True):
        st.markdown("""
**Utilization** = `Employee Count Predicted / Total Capacity` per floor per day (weekdays only).

| Risk Label | Condition | Meaning |
|------------|-----------|---------|
| 🔴 Over Capacity | Peak utilization > 90% | At least one weekday exceeds 90% of floor capacity |
| 🟡 Watch | Avg utilization > 75% | Average occupancy is high — approaching constraint |
| 🔵 Under-utilized | Avg utilization < 60% | Floor running well below capacity — consolidation candidate |
| 🟢 Healthy | Everything else | Normal operating range |

**"Peak"** = the single highest-footfall weekday in the selected horizon window.

**"Avg"** = mean daily predicted attendance across all weekdays in the window.

**Over-allocation** (static check, separate from utilization):
`SUM(Allocated Seats per floor) > Total Capacity` — a floor is over-allocated when LOBs have been
assigned more seats in aggregate than the floor physically holds.

**LOB seat gap (static):** `Allocated Seats − LOB Headcount` — answers whether an LOB has enough
allocated seats for its current headcount, ignoring attendance patterns.
""")

    with st.expander("6 · How Insights Are Generated", expanded=True):
        st.markdown("""
Insights are **rule-based bullets** generated automatically from the data — no AI or language model involved.

---

#### Short-Term Insights

Runs over the selected horizon (30 or 60 days), weekdays only.

| Priority | Check | Threshold | Output |
|---|---|---|---|
| 1 | Over-capacity risk | avg utilization ≥ 85% | ⚠️ Building at risk with peak date |
| 2 | Friday vs Wednesday dip | Always if both DOW values exist | 📉 DOW attendance pattern |
| 3 | Under-utilized building | avg utilization < 60% | 📊 Consolidation candidate |
| 4 (fallback) | No issues | — | ✅ All buildings within normal range |

Note: over-capacity insight fires at avg ≥ **85%** (earlier than the 90% Risk label) to give advance warning.
Insights operate at **building level**, not floor level.

---

#### Scenario Planner — Live Impact Insights

Compares baseline prediction vs adjusted scenario over the event window.

| # | Shown when | Output |
|---|---|---|
| 1 | delta ≠ 0 | Total attendance change over event period |
| 2 | always | Count of additional peak-risk days (>90% capacity) |
| 3 | always | Avg daily attendance change (seats/day) |
| 4 | any building impacted | Top impacted building by % change |
| 5 | scope narrowed | Count of buildings/LOBs affected |
""")
