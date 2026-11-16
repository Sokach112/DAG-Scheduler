# Scheduler Project — Outline

## 1. Design Decisions (locked in)

| Topic | Decision |
|---|---|
| Graph node identity | `str` (`eid`) everywhere, both public API and internal adjacency |
| Time unit | Integer **minutes**, relative to a plan-level `origin` |
| `Event.start` | Hard constraint: earliest allowed start (datetime) |
| `Event.deadline` | Latest finish (datetime) |
| CPM state | Stored on `Event`: `est/eft/lst/lft/slack`, all `int` minutes |
| `Event` equality | By `eid` (`__eq__` + `__hash__`) |
| Cycle detection | Delegated to `graphxlib.UnweightedGraph.topological_sort` |
| Exceptions | `CycleError`, `DuplicateIDError` |

---

## 2. Project Structure

```
scheduler/
├── models.py          # Event (done, minor fixes pending)
├── helper.py          # SchedulerHelper + EventFactory (done)
├── plan.py            # Plan: origin, to_offset / to_datetime  ← NEW
├── cpm.py             # CPMScheduler: forward/backward/critical path ← NEW
├── parallel.py        # ParallelScheduler: multi-worker simulation ← LATER
├── analysis.py        # Deadlines, gantt, reports ← NEW
├── serializer.py      # JSON/CSV/iCal I/O ← LATER
└── cli.py             # Optional command-line entry ← LATER
```

---

## 3. Module-by-Module Plan

### 3.1 `models.py` — fixes pending

- [x] `__eq__(self, other: object)` → `isinstance` guard + `NotImplemented`
- [x] Drop hand-written `__le__`/`__gt__`/`__ge__`; keep `__lt__` + `__eq__` (or use `@total_ordering`)
- [x] Docstring on `__lt__` clarifying priority direction (ascending = higher priority)
- [x] Optional: `repr` includes `est`/`eft`

### 3.2 `plan.py` — new, prerequisite for CPM

```python
class Plan:
    events: List[Event]
    origin: datetime.datetime        # tz-aware, est=0 reference

    def to_offset(self, dt) -> int   # minutes from origin
    def to_datetime(self, offset) -> datetime
    def index(self) -> Dict[str, Event]      # delegates to SchedulerHelper
    def topo_order(self) -> List[str]
```

- [x] Validate all `start`/`deadline` share `origin.tzinfo`
- [x] Validate `start >= origin` (else negative offset — decide: clamp or error)
- [x] Validate `deadline >= start`

### 3.3 `cpm.py` — Critical Path Method

```python
class CPMScheduler:
    def __init__(self, plan: Plan)
    def forward_pass(self) -> None
        # est = max(predecessor eft, to_offset(start)), eft = est + duration
    def backward_pass(self) -> None
        # lft = min(successor lst, to_offset(deadline)), lst = lft - duration
        # slack = lst - est
    def run(self) -> CPMResult
    def critical_path(self) -> List[str]
    def makespan(self) -> int
```

- [x] `backward_pass` needs successor index (reuse `events_to_adjacency`)
- [x] Decide `lft` default for leaf nodes: `to_offset(deadline)` vs `makespan`
- [x] `CPMResult` dataclass: `makespan`, `critical_path`, `events`

### 3.4 `analysis.py` — reports

```python
def check_deadlines(plan: Plan) -> List[DeadlineViolation]
def feasibility_report(plan: Plan) -> FeasibilityReport
def gantt_data(plan: Plan) -> List[dict]           # {id, start_iso, end_iso, critical}
def render_gantt_text(plan: Plan, width=80) -> str
def to_dot(plan: Plan) -> str
def to_mermaid(plan: Plan) -> str
def upstream_chain(plan: Plan, eid: str) -> List[str]
def what_if(plan: Plan, eid: str, new_duration: int) -> CPMResult
```

- [ ] `check_deadlines`: compare `eft` vs `to_offset(deadline)`
- [ ] `gantt_data`: convert offsets back via `plan.to_datetime`

### 3.5 `parallel.py` — multi-worker (later)

```python
class ParallelScheduler:
    def __init__(self, plan: Plan, workers: int, key: Callable = None)
    def run(self) -> ScheduleResult
        # event-driven: ready heap + running heap, advance clock
```

- [x] Ready selection key: `(priority, deadline_offset, eid)`
- [x] Respect `start` hard constraint when dispatching
- [x] Report per-worker timeline

### 3.6 `serializer.py` — I/O (later)

```python
def load_from_json(path) -> Plan          # id-based, two-pass construction
def save_to_json(plan, path) -> None
def to_ical(plan) -> str
```

- [ ] Two-pass: create all Events by eid, then wire `dependencies`
- [ ] Serialize `dependencies` as `List[str]` of eids

---

## 4. Implementation Order

| Phase | Deliverable | Depends on |
|---|---|---|
| **P0** | `models.py` fixes | — |
| **P1** | `plan.py` (origin, offset conversion, validation) | P0 |
| **P2** | `cpm.py` forward/backward/critical path | P1 |
| **P3** | `analysis.py` deadlines + gantt data | P2 |
| **P4** | `serializer.py` JSON round-trip | P1 |
| **P5** | `parallel.py` multi-worker | P2 |
| **P6** | `cli.py` + text gantt / DOT | P3 |

Minimum viable line: **P0 → P1 → P2 → P3** gives makespan + critical path + deadline violations + gantt data.

---

## 5. Open Questions to Resolve Before P2

1. **Leaf `lft` default**: `to_offset(deadline)` or `makespan`? (Affects slack of terminal tasks.)
2. **`start < origin`**: clamp to 0, or raise? (Negative offset is nonsensical.)
3. **`deadline` missing / optional?** If a task has no hard deadline, how to represent — `None` or a sentinel far-future offset?
4. **Tz-aware enforcement**: require all datetimes tz-aware and same tz, or allow naive (local time assumption)?

---

## 6. Non-Goals (for now)

- Working-calendar / business-hours scheduling (continuous time only)
- Resource leveling beyond worker count
- Probabilistic durations (PERT)
- Persistence beyond JSON

---
