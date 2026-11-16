# tests/test_analysis.py
import datetime
import pytest
from zoneinfo import ZoneInfo

from models import Event
from plan import Plan
from cpm import CPMScheduler
from analysis import (
    gantt_data,
    deadline_violations,
    feasibility_report,
    render_gantt_text,
    FeasibilityReport,
    _human_minutes,
    _status,
)

TZ = ZoneInfo("Asia/Shanghai")
ORIGIN = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=TZ)


# ---------- fixtures ----------
def dt(minutes: int) -> datetime.datetime:
    return ORIGIN + datetime.timedelta(minutes=minutes)


def make_event(eid, dur=10, priority=0, start_min=0, deadline_min=10_000,
               deps=None) -> Event:
    return Event(
        eid=eid, description=eid, duration=dur, priority=priority,
        start=dt(start_min), deadline=dt(deadline_min),
        dependencies=deps or [],
    )


def scheduled(events):
    """Build a Plan, run CPM, return (plan, result)."""
    plan = Plan(events, ORIGIN)
    result = CPMScheduler(plan).run()
    return plan, result


# ---------- 1. gantt_data: shape ----------
def test_gantt_data_shape():
    a = make_event("A", 30, deadline_min=60)
    b = make_event("B", 20, deps=[a], deadline_min=60)
    plan, _ = scheduled([a, b])

    rows = gantt_data(plan)
    assert len(rows) == 2
    for row in rows:
        assert set(row) == {
            "eid", "description", "start", "end",
            "duration", "priority", "status", "slack",
        }
        # ISO strings must round-trip
        datetime.datetime.fromisoformat(row["start"])
        datetime.datetime.fromisoformat(row["end"])


# ---------- 2. gantt_data: status ----------
def test_gantt_data_status():
    # A: critical (slack == 0)
    # B: normal   (slack > 0)
    # C: overdue  (slack < 0)
    a = make_event("A", 30, deadline_min=30)       # exactly tight
    b = make_event("B", 10, deadline_min=200)      # loose
    c = make_event("C", 50, deadline_min=20)       # impossible
    plan, _ = scheduled([a, b, c])

    status = {row["eid"]: row["status"] for row in gantt_data(plan)}
    assert status["A"] == "critical"
    assert status["B"] == "normal"
    assert status["C"] == "overdue"


# ---------- 3. gantt_data: sorted by start ----------
def test_gantt_data_sorted_by_start():
    a = make_event("A", 10, start_min=50, deadline_min=200)
    b = make_event("B", 10, start_min=10, deadline_min=200)
    c = make_event("C", 10, start_min=30, deadline_min=200)
    plan, _ = scheduled([a, b, c])

    eids = [row["eid"] for row in gantt_data(plan)]
    assert eids == ["B", "C", "A"]


# ---------- 4. deadline_violations: empty ----------
def test_deadline_violations_empty():
    a = make_event("A", 10, deadline_min=100)
    b = make_event("B", 10, deps=[a], deadline_min=100)
    plan, _ = scheduled([a, b])
    assert deadline_violations(plan) == []


# ---------- 5. deadline_violations: populated + sorted ----------
def test_deadline_violations_sorted():
    a = make_event("A", 50, deadline_min=20)       # late 30
    b = make_event("B", 80, deadline_min=10)       # late 70
    c = make_event("C", 10, deadline_min=100)      # on time
    plan, _ = scheduled([a, b, c])

    v = deadline_violations(plan)
    assert [r["eid"] for r in v] == ["B", "A"]     # late desc
    assert v[0]["late_minutes"] == 70
    assert v[1]["late_minutes"] == 30
    assert v[0]["late_human"] == "1h 10m"
    assert v[0]["deadline"] == 10
    assert v[0]["eft"] == 80


# ---------- 6. feasibility_report: feasible ----------
def test_feasibility_report_feasible():
    a = make_event("A", 30, deadline_min=60)
    b = make_event("B", 20, deps=[a], deadline_min=60)
    plan, result = scheduled([a, b])

    rep = feasibility_report(plan, result)
    assert isinstance(rep, FeasibilityReport)
    assert rep.is_feasible is True
    assert rep.overdue_count == 0
    assert rep.overdue == []
    assert rep.event_count == 2


# ---------- 7. feasibility_report: infeasible ----------
def test_feasibility_report_infeasible():
    a = make_event("A", 50, deadline_min=20)       # overdue
    plan, result = scheduled([a])

    rep = feasibility_report(plan, result)
    assert rep.is_feasible is False
    assert rep.overdue_count == 1
    assert rep.overdue[0]["eid"] == "A"


# ---------- 8. feasibility_report: makespan ----------
def test_feasibility_report_makespan():
    a = make_event("A", 90, deadline_min=200)
    b = make_event("B", 30, deps=[a], deadline_min=200)
    plan, result = scheduled([a, b])

    rep = feasibility_report(plan, result)
    assert rep.makespan == result.makespan == 120
    assert rep.makespan_human == "2h"


# ---------- 9. render_gantt_text: empty ----------
def test_render_gantt_empty():
    plan, _ = scheduled([])
    assert render_gantt_text(plan) == "(empty plan)"


# ---------- 10. render_gantt_text: single event ----------
def test_render_gantt_single():
    a = make_event("A", 30, deadline_min=200)
    plan, _ = scheduled([a])

    out = render_gantt_text(plan)
    lines = out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("A")
    assert "█" in lines[0]


# ---------- 11. render_gantt_text: milestone ----------
def test_render_gantt_milestone():
    a = make_event("A", 30, deadline_min=200)
    m = make_event("M", 0, deps=[a], deadline_min=200)
    plan, _ = scheduled([a, m])

    out = render_gantt_text(plan)
    assert "◆" in out


# ---------- 12. render_gantt_text: LATE tag ----------
def test_render_gantt_late_tag():
    a = make_event("A", 50, deadline_min=20)       # overdue
    plan, _ = scheduled([a])

    out = render_gantt_text(plan)
    assert "[LATE]" in out


# ---------- 13. _human_minutes ----------
@pytest.mark.parametrize("minutes,expected", [
    (0, "0m"),
    (1, "1m"),
    (59, "59m"),
    (60, "1h"),
    (90, "1h 30m"),
    (120, "2h"),
    (-20, "-20m"),
    (-90, "-1h 30m"),
])
def test_human_minutes(minutes, expected):
    assert _human_minutes(minutes) == expected


# ---------- 14. _status (unit-level) ----------
@pytest.mark.parametrize("slack,expected", [
    (-1, "overdue"),
    (-100, "overdue"),
    (0, "critical"),
    (1, "normal"),
    (999, "normal"),
])
def test_status(slack, expected):
    e = make_event("X")
    e.slack = slack
    assert _status(e) == expected
