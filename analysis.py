"""Read-only reports over a CPM-scheduled Plan.

All functions assume CPMScheduler(plan).run() has been called and do NOT
recompute CPM, mutate Events, or reset scheduling state. Callers are
responsible for running CPM first.

Offsets (est/eft/lst/lft/slack) are integer minutes relative to
Plan.origin. Absolute times are obtained via Plan.to_datetime().
"""

from dataclasses import dataclass
from typing import List, Dict, Literal

from models import Event
from plan import Plan
from cpm import CPMResult


EventStatus = Literal["critical", "overdue", "normal"]


# ---------- helpers ----------
def _status(e: Event) -> EventStatus:
    if e.slack < 0:
        return "overdue"
    if e.slack == 0:
        return "critical"
    return "normal"


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


# ---------- structured data ----------
def gantt_data(plan: Plan) -> List[Dict]:
    """One dict per event, with absolute ISO times and status."""
    rows = []
    for e in plan.events:
        rows.append({
            "eid": e.eid,
            "description": e.description,
            "start": plan.to_datetime(e.est).isoformat(),
            "end": plan.to_datetime(e.eft).isoformat(),
            "duration": e.duration,
            "priority": e.priority,
            "status": _status(e),
            "slack": e.slack,
        })
    rows.sort(key=lambda r: (r["start"], r["eid"]))
    return rows


def deadline_violations(plan: Plan) -> List[Dict]:
    """Events whose eft exceeds their deadline offset, sorted by lateness desc."""
    out = []
    for e in plan.events:
        dl = plan.deadline_offset(e)
        late = e.eft - dl
        if late > 0:
            out.append({
                "eid": e.eid,
                "eft": e.eft,
                "deadline": dl,
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


def feasibility_report(plan: Plan, result: CPMResult) -> FeasibilityReport:
    """Aggregate stats. `result` is the CPMResult from a prior run()."""
    overdue = deadline_violations(plan)
    return FeasibilityReport(
        event_count=len(plan.events),
        makespan=result.makespan,
        makespan_human=_human_minutes(result.makespan),
        critical_count=len(result.critical_path),
        overdue_count=len(overdue),
        overdue=overdue,
        is_feasible=len(overdue) == 0,
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
