# for_future/

This folder holds fully-implemented backend modules that are not yet connected
to the Streamlit UI. They are retained for the next development phase.

## Contents

### engine/
| File | Description |
|---|---|
| `allocation_engine.py` | Seat allocation logic — recommended, simple, and RTO-compliance allocations |
| `optimizer.py` | PuLP LP optimizer — optimal seat placement across floors with constraints |
| `spatial.py` | Floor assignment engine — adjacency scoring, unit-to-floor placement, consolidation suggestions |
| `scenario_engine.py` | Scenario simulation — override application, floor modifications, multi-scenario compare |
| `explainer.py` | Plain-language explanations of allocation decisions |

### models/
| File | Description |
|---|---|
| `allocation.py` | Allocation dataclasses |
| `attendance.py` | Attendance profile models |
| `audit.py` | `AuditEntry` — tracks user overrides, uploads, and resets with timestamp + rationale |
| `building.py` | `Floor` and `FloorAllocation` dataclasses |
| `scenario.py` | `Scenario`, `ScenarioOverride` dataclasses |
| `unit.py` | Unit data models |

## When to activate

These modules are designed to power a future **Seat Allocation / Optimizer** tab.
They depend on the same `daily_df` session data already loaded by the app.
Wire them in by importing from `for_future/engine/` and building a new tab in `tabs/`.
