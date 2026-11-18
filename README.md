# DAG Scheduler

**Author: Limitless**

DAG-based task scheduler with Critical Path Method (CPM) and
resource-constrained scheduling.

All scheduling offsets (`est`, `eft`, `lst`, `lft`, `slack`) are integer
minutes relative to a plan-level `origin`. Absolute times (`start`,
`deadline`) are timezone-aware `datetime` values.

## Features

- **CPM**: forward/backward pass, earliest/latest times, slack, critical path,
  makespan, max concurrency
- **Resource-constrained scheduling**: list scheduling with N workers
- **Analysis**: gantt data, deadline violations, feasibility report, ASCII
  gantt, Graphviz DOT, Mermaid flowchart
- **Serialization**: versioned JSON I/O for plans

## Installation

```bash
pip install dag-scheduler
```

Requires Python >= 3.10. Depends on [`graphxlib`](https://pypi.org/project/graphxlib/).

## Quick start

```python
import datetime
from zoneinfo import ZoneInfo

from dag_scheduler import (
    Event, Plan, CPMScheduler,
    gantt_data, feasibility_report,
)

origin = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

def dt(minutes):
    return origin + datetime.timedelta(minutes=minutes)

design = Event("design", "Design", duration=60, priority=1,
               start=dt(0), deadline=dt(180))
build = Event("build", "Build", duration=120, priority=2,
              start=dt(0), deadline=dt(300), dependencies=[design])
test = Event("test", "Test", duration=30, priority=3,
             start=dt(0), deadline=dt(300), dependencies=[build])

plan = Plan([design, build, test], origin)
result = CPMScheduler(plan).run()

print("Makespan:", result.makespan)
print("Critical path:", result.critical_path)
print("Max concurrency:", result.max_concurrency)
print("Feasible:", feasibility_report(plan, result).is_feasible)

for row in gantt_data(plan):
    print(row["eid"], row["start"], "->", row["end"], row["status"])
```

## Modules

| Module | Purpose |
|---|---|
| `models` | `Event` data model |
| `plan` | Time coordinate system and validation |
| `cpm` | Critical Path Method |
| `parallel` | Resource-constrained scheduling |
| `analysis` | Read-only reports and exports |
| `serializer` | Versioned JSON I/O |

## Data Flow

```text
   events: List[Event]
        │
        v
   Plan(events, origin)          <- Check the uniqueness of eid, the existence of dependency
        │  plan.index: Dict[str, Event]
        │  plan.origin: datetime.datetime
        v
   CPMScheduler(plan)            <- topo_order (cycle detect), build graph
        │
        v
   scheduler.run()               <- forward_pass + backward_pass
        │  Write back every Event: est/eft/lst/lft/slack
        v
   CPMResult                     <- makespan, critical_path, overdue, events
        │
        v
   analysis.*(plan, result)      <- Read-only
        │  gantt_data / deadline_violations / feasibility_report / render_gantt_text
        v
   List[Dict] / FeasibilityReport / str
```


## Concepts

### Time model

- All scheduling offsets (`est`, `eft`, `lst`, `lft`, `slack`) are integer
  minutes relative to `Plan.origin`.
- `start` and `deadline` are timezone-aware `datetime` values. They must be
  on whole-minute boundaries from `origin`, with `start >= origin` and
  `deadline >= start`.
- `makespan = max(eft) - min(est)`, which reflects the actual occupied span
  even when all tasks start after `origin`.

### CPM semantics

- Forward pass: `est = max(predecessor eft, start offset)`, `eft = est + duration`.
- Backward pass: `lft = min(successor lst, deadline offset)`, `lst = lft - duration`.
- `slack = lst - est`. `slack == 0` marks critical tasks; `slack < 0` marks
  overdue tasks.
- `critical_path()` returns a single connected critical chain (deterministic,
  lexicographic tie-break). `critical_events()` returns the full set of
  critical tasks.

### Resource scheduling

- `ParallelScheduler(plan, workers)` does not modify CPM fields on `Event`.
  Results live in `ResourceScheduleResult.start/end/assignments`.
- `makespan >= CPM makespan`: resource constraints can only delay.
- Default priority: `(-priority, slack, est, eid)`. Override via `priority_key`.
- CPM must run first, because the default `priority_key` reads `slack`.

### Serialization

Only inputs are persisted: `origin`, event fields, and dependency eids.
CPM outputs are recomputed after loading. The JSON format carries a `version`
field for future migrations.

## Known limitations

- Single resource type: every task occupies one worker. No per-resource
  capacities (e.g. separate kitchen and broom).
- Continuous time: no business calendar, working hours, or weekends.
- `critical_path()` returns one chain when multiple parallel critical chains
  exist. Use `critical_events()` for the full set.
- `critical_width_estimate()` is an approximation (max level width), not an
  exact max antichain.
- `ParallelScheduler` is a list-scheduling heuristic and does not guarantee
  optimal makespan.
- Serialization persists inputs only; CPM outputs are not stored.

## 🐳 Running with Docker

### Option 1: Docker Compose (Recommended)

The easiest way to run the API is using Docker Compose.

```bash
# Build and start the container in the background
docker compose up -d

# View logs
docker compose logs -f api

# Stop and remove the container
docker compose down
```

### Option 2: Docker CLI

If you prefer plain Docker commands:

```bash
docker build -t dag-scheduler-api .
docker run -p 8000:8000 dag-scheduler-api
```

### Configuration

- **CORS**: By default, the API allows all origins (CORS_ORIGINS=*). In production, set this environment variable to your frontend domain (e.g., CORS_ORIGINS=https://your-app.com).

- **In-memory store**: Plans are stored in memory. Restarting the container will lose all plans. This setup runs a single worker (--workers 1). To scale horizontally, you will need a persistent store (e.g., Redis) and a load balancer.

## License

MIT License

Copyright (c) 2026 Limitless

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

