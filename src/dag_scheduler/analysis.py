"""Read-only reports over a CPM-scheduled Plan.

All functions assume CPMScheduler(plan).run() has been called and do NOT
recompute CPM, mutate Events, or reset scheduling state. Callers are
responsible for running CPM first.

Offsets (est/eft/lst/lft/slack) are integer minutes relative to
Plan.origin. Absolute times are obtained via Plan.to_datetime().
"""

import copy
import datetime
from dataclasses import dataclass
from typing import List, Dict, Literal, Optional
from .models import Event
from .plan import Plan
from .cpm import CPMScheduler, CPMResult
from collections import defaultdict


EventStatus = Literal["critical", "overdue", "normal"]


# ---------- helpers ----------
def _safe_id(eid: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in eid)


def _status(e: Event,
            project_deadline_offset: Optional[int] = None) -> EventStatus:
    if project_deadline_offset is not None and e.eft > project_deadline_offset:
        return "overdue"
    if e.slack < 0:
        return "overdue"
    if e.slack == 0:
        return "critical"
    return "normal"


# Public alias for API layers; _status remains for backwards compatibility.
event_status = _status


def _human_minutes(m: int) -> str:
    """90 -> '1h 30m', -20 -> '-20m', 0 -> '0m'."""
    sign = "-" if m < 0 else ""
    m = abs(m)
    h, mm = divmod(m, 60)
    if h and mm:
        return f"{sign}{h}h {mm}m"
    if h:
        return f"{sign}{h}h"
    return f"{sign}{mm}m"


def critical_width_estimate(plan: Plan,
                            order: Optional[List[str]] = None) -> int:
    """Approximate max parallelism of the critical subgraph.

    Groups critical tasks by topological level and returns the largest
    level width. This is a lower bound on the resources needed to run
    all critical tasks without delay; it is NOT the exact max antichain.

    Pass `order` (e.g. scheduler.order) to avoid recomputing the
    topological order. Returns 0 if no task has slack == 0.
    """
    critical = {e.eid for e in plan.events if e.slack == 0}
    if not critical:
        return 0

    order = order or plan.topo_order()
    level: Dict[str, int] = {}
    for eid in order:
        if eid not in critical:
            continue
        preds = [d.eid for d in plan.index[eid].dependencies
                 if d.eid in critical]
        level[eid] = 1 + max((level[p] for p in preds), default=-1)

    width = defaultdict(int)
    for lv in level.values():
        width[lv] += 1
    return max(width.values(), default=0)

# ---------- structured data ----------
def gantt_data(plan: Plan,
               project_ddl: Optional[datetime.datetime] = None) -> List[Dict]:
    """One dict per event, with absolute ISO times and status."""
    project_deadline_offset = (
        plan.to_offset(project_ddl) if project_ddl is not None else None)
    rows = []
    for e in plan.events:
        rows.append({
            "eid": e.eid,
            "description": e.description,
            "start": plan.to_datetime(e.est).isoformat(),
            "end": plan.to_datetime(e.eft).isoformat(),
            "duration": e.duration,
            "priority": e.priority,
            "status": _status(e, project_deadline_offset),
            "slack": e.slack,
        })
    rows.sort(key=lambda r: (r["start"], r["eid"]))
    return rows


def deadline_violations(
        plan: Plan,
        project_ddl: Optional[datetime.datetime] = None) -> List[Dict]:
    """Events whose eft exceeds their effective deadline, latest first.

    The effective deadline is the earlier of the event deadline and the
    project-wide deadline. Existing ``deadline`` remains the effective
    offset; the original task deadline is also reported separately.
    """
    project_deadline_offset = (
        plan.to_offset(project_ddl) if project_ddl is not None else None)
    out = []
    for e in plan.events:
        task_deadline = plan.deadline_offset(e)
        effective = task_deadline
        if (project_deadline_offset is not None
                and project_deadline_offset < effective):
            effective = project_deadline_offset
        late = e.eft - effective
        if late > 0:
            out.append({
                "eid": e.eid,
                "eft": e.eft,
                "deadline": effective,
                "task_deadline": task_deadline,
                "project_deadline": project_deadline_offset,
                "deadline_source": (
                    "project"
                    if project_deadline_offset is not None
                    and project_deadline_offset <= task_deadline
                    else "task"
                ),
                "late_minutes": late,
                "late_human": _human_minutes(late),
            })
    out.sort(key=lambda r: r["late_minutes"], reverse=True)
    return out


# ---------- aggregate report ----------
@dataclass
class FeasibilityReport:
    event_count: int
    makespan: int
    makespan_human: str
    critical_count: int
    overdue_count: int
    overdue: List[Dict]
    is_feasible: bool
    project_ddl: Optional[str] = None
    project_finish: Optional[str] = None
    project_overdue: bool = False
    project_late_minutes: int = 0
    project_late_human: str = "0m"


def feasibility_report(plan: Plan, result: CPMResult,
                       project_ddl: Optional[datetime.datetime] = None
                       ) -> FeasibilityReport:
    """Aggregate stats. `result` is the CPMResult from a prior run()."""
    overdue = deadline_violations(plan, project_ddl)
    project_deadline_offset = (
        plan.to_offset(project_ddl) if project_ddl is not None else None)
    max_eft = max((e.eft for e in plan.events), default=0)
    project_finish = plan.to_datetime(max_eft)
    project_late = (
        max(0, max_eft - project_deadline_offset)
        if project_deadline_offset is not None else 0)
    project_overdue = project_late > 0
    return FeasibilityReport(
        event_count=len(plan.events),
        makespan=result.makespan,
        makespan_human=_human_minutes(result.makespan),
        critical_count=sum(1 for e in plan.events if e.slack == 0),
        overdue_count=len(overdue),
        overdue=overdue,
        is_feasible=len(overdue) == 0 and not project_overdue,
        project_ddl=project_ddl.isoformat() if project_ddl else None,
        project_finish=project_finish.isoformat(),
        project_overdue=project_overdue,
        project_late_minutes=project_late,
        project_late_human=_human_minutes(project_late),
    )


# ---------- text rendering ----------
def render_gantt_text(plan: Plan, width: int = 80) -> str:
    """ASCII gantt. Bars are scaled to [min(est), max(eft)]."""
    if not plan.events:
        return "(empty plan)"

    left = min(e.est for e in plan.events)
    right = max(e.eft for e in plan.events)
    span = max(right - left, 1)

    label_w = max(len(e.eid) for e in plan.events) + 2
    bar_w = max(width - label_w - 2, 10)  # keep some room

    lines = []
    for e in sorted(plan.events, key=lambda x: (x.est, x.eid)):
        offset = int((e.est - left) / span * bar_w)
        offset = min(offset, bar_w - 1)
        if e.duration == 0:
            bar = " " * offset + "◆"
        else:
            length = max(int(e.duration / span * bar_w), 1)
            length = min(length, bar_w - offset)
            bar = " " * offset + "█" * length
        bar = bar.ljust(bar_w)
        tag = " [LATE]" if e.slack < 0 else ""
        lines.append(f"{e.eid:<{label_w}}{bar}{tag}")

    return "\n".join(lines)


# ---------- dot rendering ----------
def to_dot(plan: Plan, result: Optional[CPMResult] = None) -> str:
    """Graphviz DOT. Color by status; bold the critical_path chain if
    result is given."""
    chain = set(result.critical_path) if result else set()

    lines = ["digraph plan {"]
    lines.append("  rankdir=LR;")
    lines.append('  node [shape=box, style=rounded];')

    for e in plan.events:
        if e.slack < 0:
            color = "red"
        elif e.slack == 0:
            color = "orange"
        else:
            color = "black"
        desc = e.description.replace('"', '\\"').replace("\n", " ")
        label = f"{e.eid}\\n{desc}\\n{e.duration}m"
        attrs = f'label="{label}", color="{color}"'
        if e.eid in chain:
            attrs += ", penwidth=3, fontname=\"Helvetica-Bold\""
        lines.append(f'  "{e.eid}" [{attrs}];')

    for e in plan.events:
        for dep in e.dependencies:
            lines.append(f'  "{dep.eid}" -> "{e.eid}";')

    lines.append("}")
    return "\n".join(lines)


# ---------- mermaid rendering ----------
def to_mermaid(plan: Plan, result: Optional[CPMResult] = None) -> str:
    """Mermaid flowchart. Color by status; bold the critical_path chain
    if result is given."""
    chain = set(result.critical_path) if result else set()
    safe = {e.eid: _safe_id(e.eid) for e in plan.events}

    lines = ["flowchart LR"]
    for e in plan.events:
        sid = safe[e.eid]
        if e.slack < 0:
            style = "fill:#fdd,stroke:#c00"
        elif e.slack == 0:
            style = "fill:#ffe,stroke:#e80"
        else:
            style = "fill:#fff,stroke:#333"
        if e.eid in chain:
            style += ",stroke-width:3px"
        label = f"{e.eid}<br/>{e.description}"
        lines.append(f'  {sid}["{label}"]')
        lines.append(f"  style {sid} {style}")

    for e in plan.events:
        for dep in e.dependencies:
            lines.append(f"  {safe[dep.eid]} --> {safe[e.eid]}")

    return "\n".join(lines)


def what_if(plan: Plan, eid: str, new_duration: int) -> dict:
    """Compare CPM makespan before/after changing one event's duration.

    Returns a dict with old/new makespan, delta, and critical paths.
    Does not mutate the original plan.

    Raises:
        KeyError: if eid is not in the plan.
        ValueError: if new_duration is negative.
    """
    if eid not in plan.index:
        raise KeyError(f"unknown eid: {eid}")
    if new_duration < 0:
        raise ValueError("new_duration must be >= 0")

    old = CPMScheduler(plan).run()

    new_plan = copy.deepcopy(plan)
    new_plan.index[eid].duration = new_duration
    new = CPMScheduler(new_plan).run()

    return {
        "eid": eid,
        "old_duration": plan.index[eid].duration,
        "new_duration": new_duration,
        "old_makespan": old.makespan,
        "new_makespan": new.makespan,
        "delta": new.makespan - old.makespan,
        "old_critical_path": old.critical_path,
        "new_critical_path": new.critical_path,
    }
