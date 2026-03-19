"""Help tab — reference guide for calculations, formulas, and thresholds."""


def render() -> None:
    import streamlit as st

    st.markdown("### 📖 How This App Works")
    st.caption("Reference guide for all calculations, formulas, and thresholds used across the app.")

    with st.expander("1 · Data Model", expanded=True):
        st.markdown("""
**Required columns** (for both sample data and uploaded CSV):

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Calendar date of the record |
| `building_id` | string | Unique building identifier (e.g. `BLR-1`) |
| `building_name` | string | Human-readable building name |
| `city` | string | City the building is in |
| `lob` | string | Line of Business occupying the building / tower |
| `footfall` | integer | Number of people in office on that date |
| `capacity` | integer | Total seat capacity of the tower (or building) |

**Optional columns** (present in sample data; absent = graceful degradation):

| Column | Type | Description |
|--------|------|-------------|
| `tower_id` | string | Unique tower identifier (e.g. `BLR-1-TA`) |
| `tower_name` | string | Human-readable tower name (e.g. `Tower A`) |
| `floor_count` | integer | Number of floors in the tower (metadata; no UI filter) |

`utilization_pct` is derived automatically: `footfall ÷ capacity` (clipped at 130%).

**Sample dataset:** 27 towers across 12 buildings in 4 cities (Bangalore, Hyderabad, Chennai, Manila) ·
~9,855 rows (27 towers × 365 days) · Deterministic (seed = 42 — same data every load).

**Hierarchy:** City → Building (3 per city) → Tower (2–3 per building) → Floor (10 per tower, metadata only).

**Uploaded CSV:** Must include all 7 required columns above. Optional tower/floor columns are supported.
Future-dated rows are used as projections. Historical-only files will show actuals, not forecasts, in horizon views.
""")

    with st.expander("2 · How the Horizon Works", expanded=True):
        st.markdown("""
Both Short-Term and Long-Term views **slice the dataset** to a date window starting from today. No extrapolation is performed.

| Tab | Horizon option | Date range used |
|-----|---------------|-----------------|
| Short-Term | 30 days | `today ≤ date < today + 30` |
| Short-Term | 60 days | `today ≤ date < today + 60` |
| Long-Term | 6 months | `today ≤ date < today + 180` |
| Long-Term | 12 months | `today ≤ date < today + 365` |

**All KPIs and charts use weekdays only (Mon–Fri).** Weekends are excluded from every calculation.

**Why numbers change between horizons:** The sample data has a linear growth trend baked in.
Days further in the future have a slightly higher footfall multiplier, so a 60-day window will show
higher peak/avg values than a 30-day window for growing towers. Shrinking towers (e.g. TIDEL Park
Operations, −4% growth) show the opposite.
""")

    with st.expander("3 · How Forecasting Works", expanded=True):
        st.markdown("""
**There is no statistical forecasting model** (no ARIMA, Holt-Winters, or Prophet) in this version.

The sample data is generated with a deterministic formula at load time:

```
footfall = base_demand × DOW_multiplier × trend_factor × noise

base_demand    = base_utilization × capacity
                 (e.g. 84% × 200 seats = 168 baseline seats for BLR-1-TA)

trend_factor   = 1.0 + annual_growth_rate × (day_number / 365)
                 (linear ramp; e.g. +16%/yr means day 365 = 1.16×)

DOW_multiplier = Mon 0.85 · Tue 1.00 · Wed 1.00 · Thu 0.95 · Fri 0.75
                 Sat 0.05 · Sun 0.02

noise          = 1 + Normal(mean=0, std=0.08)   ← ±8% random variation
                 seed = 42 → same numbers every load
```

**For uploaded data:** The app reads whatever footfall values are in your file. If your file contains
future projections, those are displayed as-is. If it is historical only, the horizon views will be
empty (no future rows to slice).
""")

    with st.expander("4 · Scenario Planner Calculations", expanded=True):
        st.markdown("""
#### Mode A — Event Impact

The baseline is your filtered dataset, unmodified. An adjustment multiplier is applied to footfall rows
that fall **within the event date window** and **within the selected scope**:

```
combined_multiplier = event_mult_1 × event_mult_2 × … × (1 + custom_pct / 100)

scenario_footfall = baseline_footfall × combined_multiplier
    — applied only to: rows where date ∈ [event_start, event_end]
                   AND building/LoB matches the selected scope
```

**Default event multipliers** (configurable in ⚙️ Admin → Scenario Adjustment Configuration):

| Event | Default Multiplier | Effect |
|-------|-----------|--------|
| Townhall | ×1.20 | +20% footfall |
| Leadership Visit | ×1.15 | +15% footfall |
| Weather Alert | ×0.70 | −30% footfall |
| Traffic / Local Disruption | ×0.80 | −20% footfall |
| Mandatory Holiday | ×0.10 | −90% footfall |
| Optional Holiday | ×0.60 | −40% footfall |
| US Holiday | ×0.75 | −25% footfall |

Admins can edit, add, or remove event types from the **Admin tab → Scenario Adjustment Configuration** section.
Changes apply immediately without a data reload.

Multiple events combine multiplicatively: e.g. Townhall + Optional Holiday = 1.20 × 0.60 = ×0.72 (net −28%).

**KPI cards** show **avg daily footfall (seats/day)** — the same unit as the chart Y-axis.
The total person-days impact over the full event window is shown as a sub-caption.

#### Mode B — Policy Simulation

All footfall is scaled linearly relative to the baseline RTO assumption (3.5 days/week):

```
scenario_footfall = baseline_footfall × (new_rto_days / 3.5)
```

Seat gap per building = `capacity − (peak_footfall ÷ target_utilization%)`
- Positive gap = surplus seats available
- Negative gap = seats deficit (capacity expansion needed)

#### Download Impact Report (.xlsx)

Both modes offer a download button that generates a 4-sheet Excel workbook:
- **Summary** — KPI metrics and mode parameters
- **Building Impact** — per-building footfall delta table
- **Daily Data** — day-by-day baseline vs scenario footfall + delta
- **Insights** — structured insight bullets
""")

    with st.expander("5 · Risk Thresholds & Utilization", expanded=True):
        st.markdown("""
**Utilization** is always computed as weekday footfall ÷ capacity, then averaged or peaked over the horizon window.

| Risk Label | Condition | Meaning |
|------------|-----------|---------|
| 🔴 Over Capacity | Peak utilization > 90% | At least one day exceeds 90% of capacity in the window |
| 🟡 Watch | Avg utilization > 75% | Average occupancy is high — approaching constraint |
| 🔵 Under-utilized | Avg utilization < 60% | Building is running well below capacity — consolidation candidate |
| 🟢 Healthy | Everything else | Normal operating range |

**"Peak"** = the single highest-footfall weekday within the horizon window.

**"Avg"** = mean daily footfall across all weekdays in the horizon window.

These thresholds are applied in:
- Short-Term KPI cards ("Buildings >90%", "Buildings <60%")
- Building Risk Details drilldown table
- Auto-generated Insights bullets
- Long-Term insights ("projected to exceed 90% avg utilization by…")
""")

    with st.expander("6 · How Insights Are Generated", expanded=True):
        st.markdown("""
Insights are rule-based bullets generated automatically from the data — no AI or language model is involved.
Each tab uses a different set of rules, threshold checks, and templates. All cap at **5 bullets maximum**.

---

#### Short-Term Insights

Computed by `generate_insights_short_term()`. Runs over the selected horizon window (30 or 60 days), weekdays only.

**Step 1 — Per-building stats computed:**
```
avg_util  = mean(footfall / capacity)  across all weekdays in window
peak_util = max(footfall / capacity)   across all weekdays in window
peak_date = date on which peak_util occurred
```

**Step 2 — Checks run in this priority order (first matches fill the 5-bullet cap):**

| Priority | Check | Threshold | Template |
|----------|-------|-----------|----------|
| 1 (highest) | Over-capacity risk | avg_util ≥ **85%** | ⚠️ **{building}** projected at {X}% avg utilization — peak on {date} |
| 2 | Friday vs Wednesday dip | Always shown if both DOW values exist | 📉 Friday footfall averages **{X}%** utilization vs **{Y}%** on Wednesday |
| 3 | Under-utilized building | avg_util < **60%** | 📊 **{building}** under-utilized at {X}% average occupancy |
| 4 (fallback) | No issues found | All above checks returned 0 results | ✅ All buildings within normal utilization range for this window. |

Note: the over-capacity trigger here is avg ≥ **85%** (not 90%) — it fires earlier than the Risk label threshold to give advance warning.

---

#### Long-Term Insights

Computed by `generate_insights_long_term()`. Runs over the full horizon (6 or 12 months), weekdays only, grouped by **calendar month**.

**Step 1 — Per-building monthly utilization computed:**
```
monthly_util = mean(footfall / capacity)  across all weekdays in each month
               (one value per building per month)
```

**Step 2 — Checks run in this priority order:**

| Priority | Check | Threshold | Template |
|----------|-------|-----------|----------|
| 1 (highest) | Capacity breach forecast | monthly_util ≥ **90%** in any month | ⚠️ **{building}** projected to exceed 90% avg utilization by **{first breach month}** |
| 2 | Consolidation candidate | overall avg monthly_util < **55%** | 📊 **{building}** projected at only {X}% avg utilization over {N} months — consider consolidation |
| 3 (fallback) | No issues found | — | ✅ Portfolio capacity appears balanced over the forecast horizon. |

---

#### Scenario Planner — Live Impact Insights

Computed by `compute_live_insights()`. Runs over the event date window, comparing baseline vs scenario DataFrames.

| # | Shown when | Calculation | Template |
|---|------------|-------------|----------|
| 1 | delta ≠ 0 | `sum(scenario) − sum(baseline)` in event window | 📊 This scenario **adds/reduces {X} total footfall** over the event period |
| 2 | always | Count days where portfolio util > 90%, compare baseline vs scenario | ⚠️ **{N} additional peak-risk days** (>90% capacity) |
| 3 | always | `total_delta / weekday_count` | 📅 Avg daily footfall change: **{±X} seats/day** |
| 4 | any building impacted | `argmax(abs(per_building_delta))` | 🏢 Top impacted building: **{name}** ({±X}%) |
| 5 | scope is narrowed | Count buildings/LoB matching scope | 🎯 Adjustment applies to **{N} of {M} buildings** |
""")
