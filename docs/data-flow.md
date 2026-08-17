# Data flow and traceability

The prototype uses controlled CSV/JSON seed inputs. It does not claim live railway operations.

| Dashboard value | API | Service/algorithm | Data source |
|---|---|---|---|
| Train state | `/simulation/state` | SimPy train process | trains, tracks, timetable seeds |
| Delay | `/metrics` | delay breakdown sum | simulated waits and scenario event |
| Conflicts | `/conflicts` | temporal/resource conflict detector | occupancy history |
| Recommendation | `/recommendations` | what-if + CP-SAT + safety validator | cloned twin states |
| Validation evidence | `/validation/runs/{id}` | validation runner | seven scenario definitions and deterministic seeds |

WebSocket messages expose the same orchestrator state; the browser does not generate operational values.
