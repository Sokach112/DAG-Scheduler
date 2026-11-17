# DAG-Scheduler — Project Outline

DAG-based task scheduler with CPM, resource-constrained scheduling, and a
FastAPI layer for frontend integration.

---

## 1. Design Decisions (locked in)

| Topic | Decision |
|--- | ---|
| Graph node identity | `str` (`eid`) everywhere, both public API and internal adjacency |
| Time unit | Integer ** minutes**, relative to a plan-level `origin` |
| `Event.start` | Hard constraint: earliest allowed start(datetime, tz-aware) |
| `Event.deadline` | Hard constraint: latest finish(datetime, tz-aware) |
| CPM state | Stored on `Event`: `est/eft/lst/lft/slack`, all `int` minutes |
| Leaf `lft` | `deadline_offset` |
| `makespan` | `max(eft) - min(est)` |
| `max_concurrency` | Max simultaneous tasks on the CPM timeline(half-open `[est, eft)`) |
| `critical_path` | One connected chain, lexicographically smallest eid sequence |
| `critical_events` | All `slack == 0` eids, topological order |
| Negative slack | Allowed
`slack < 0` means overdue |
| `duration == 0` | Allowed(milestone, no concurrency slot) |
| `Event` equality | By `eid` (`__eq__` + `__hash__`) |
| Cycle detection | Delegated to `graphxlib.UnweightedGraph.topological_sort` |
| Serialization | Inputs only
CPM outputs recomputed on load |
| Package layout | `src/dag_scheduler/` (core) + `src/api/` (FastAPI, parallel) |

---

## 2. Project Structure

```
DAG-Scheduler/
├── pyproject.toml
├── README.md
├── outline.md
├── src/
│   ├── dag_scheduler/
│   │   ├── __init__.py
│   │   ├── models.py          # Event
│   │   ├── helper.py          # SchedulerHelper, EventFactory
│   │   ├── plan.py            # Plan
│   │   ├── cpm.py             # CPMScheduler, CPMResult
│   │   ├── analysis.py        # gantt_data, feasibility_report, to_dot, ...
│   │   ├── parallel.py        # ParallelScheduler (single resource)
│   │   └── serializer.py      # plan_to_dict / plan_from_dict / JSON I/O
│   └── api/
│       ├── __init__.py
│       ├── app.py             # FastAPI endpoints
│       └── store.py           # in-memory PlanSession store
└── tests/
    ├── test_plan.py
    ├── test_cpm.py
    ├── test_analysis.py
    ├── test_parallel.py
    ├── test_serializer.py
    └── test_api.py
```

---

## 3. Completed Modules

### `models.py`
- `Event` with `eid`, `description`, `duration` (int min), `priority`,
`start` / `deadline` (tz-aware datetime), `dependencies`,
`est/eft/lst/lft/slack`.
- `__eq__` / `__hash__` by `eid`
`__lt__` by `(-priority, start, deadline, eid)`.

### `helper.py`
- `SchedulerHelper.events_to_adjacency` (`dep_eid -> [succ_eid]`).
- `events_to_index` with duplicate / missing-dependency validation.
- `topo_order` (delegates to `graphxlib`).
- `upstream_dependencies` / `downstream_dependents` / `direct_successors`.
- `EventFactory` with id-collision guard.

### `plan.py`
- `Plan(events, origin)`: tz-aware origin, integer-minute validation,
`start >= origin`, `deadline >= start`, whole-minute offsets.
- `to_offset` / `to_datetime` / `start_offset` / `deadline_offset`.
- `topo_order()` convenience wrapper.

### `cpm.py`
- `CPMScheduler`: `forward_pass`, `backward_pass`, `run`.
- `CPMResult`: `makespan`, `max_concurrency`, `critical_path`
(single chain), `overdue`, `events`.
- `critical_events()` returns the full `slack == 0` set.

### `analysis.py`
- `gantt_data`, `deadline_violations`, `feasibility_report`.
- `critical_width_estimate` (topological level width approximation).
- `render_gantt_text`.
- `to_dot` / `to_mermaid` with critical-chain highlight.

### `parallel.py`
- `ParallelScheduler(plan, workers)`, list scheduling with priority heap.
- `ResourceScheduleResult`: `makespan`, `workers`, `start`, `end`,
`assignments`.
- Default `priority_key = (-priority, slack, est, eid)`.

### `serializer.py`
- `plan_to_dict` / `plan_from_dict` / `save_to_json` / `load_from_json`.
- Format `version: 1`
dependencies stored as eid lists.
- `SerializationError` for format problems
`ValueError` for Plan business
validation passes through unwrapped.

### `api/`
- `POST / plan`, `GET / plans`, `GET / plan/{id}`,
`GET / plan/{id}/gantt`, `GET / plan/{id}/report`,
`GET / plan/{id}/schedule?workers = N`,
`GET / plan/{id}/graph?format = mermaid | dot`, `DELETE / plan/{id}`.
- CORS via `CORS_ORIGINS` env var(default `*`).
- Unified error format `{"error": {"status": ..., "detail": ...}}`
422 keeps structured Pydantic `errors()`.

---

## 4. Pending / TODO

### P6.5 — Frontend integration readiness
- [] Dynamic route listing for `GET / ` (from `app.routes`).
- [] Production CORS: set `CORS_ORIGINS` env var.
- [] Error format contract documented in README.
- [] Consider `response_model` Pydantic schemas for OpenAPI richness.

### P7 — Feature enhancements
- [] `what_if(plan, eid, new_duration)`: clone Plan, recompute, diff.
- [] `resource_gantt_data(result)` in `analysis.py`.
- [] API endpoint `POST / plan/{id}/what-if `.
- [] API endpoint `GET / plan/{id}/schedule/gantt`.

### P8 — Robustness
- [] Plan: validate `dependencies` has no duplicates.
- [] `pytest-timeout` on all tests(already configured at 10s).
- [] `ParallelScheduler`: document `priority_key` purity requirement.

### P9 — Deployment
- [] Dockerfile.
- [] Production `uvicorn` config(`--workers N`).
- [] Health check endpoint `/healthz`.
- [] Structured request logging.

### P10 — Multi-resource (deferred, needs explicit demand)
- [] Resource types with capacities(kitchen, broom, etc.).
- [] Task declares required resources.
- [] RCPSP heuristic / exact solver.

---

## 5. Known Limitations

- **Single resource type**: `ParallelScheduler` models "workers" only, no differentiated resources.
- **Continuous time**: no working calendar(nights/weekends counted).
- **In-memory store**: API restarts lose plans, no multi-worker session sharing.
- **`api` top-level package name**: may collide with other packages named
`api` in the same environment.
- **No auth**: API is open intended for trusted networks or behind a proxy.