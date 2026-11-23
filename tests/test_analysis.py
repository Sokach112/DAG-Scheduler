import datetime
import pytest
from zoneinfo import ZoneInfo
from dag_scheduler import Event, Plan, CPMScheduler
from dag_scheduler.analysis import (
    gantt_data,
    deadline_violations,
    feasibility_report,
    render_gantt_text,
    FeasibilityReport,
    _human_minutes,
    _status,
    to_dot,
    to_mermaid,
    what_if,
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


def test_to_dot_highlights_chain():
    a = make_event("A", 10, deadline_min=20)
    b = make_event("B", 10, deps=[a], deadline_min=20)
    plan, result = scheduled([a, b])
    dot = to_dot(plan, result)
    # A and B are on the critical path (deadline exactly tight)
    assert result.critical_path == ["A", "B"]
    assert dot.count("penwidth=3") == 2


def test_to_mermaid_safe_id():
    a = make_event("evt-001", 10, deadline_min=20)
    plan, _ = scheduled([a])
    mm = to_mermaid(plan)
    assert "evt_001[" in mm
    assert "evt-001<" in mm       # label keeps original eid


def test_what_if_extends_makespan():
    a = make_event("A", 10, deadline_min=100)
    b = make_event("B", 20, deps=[a], deadline_min=100)
    plan = Plan([a, b], ORIGIN)
    CPMScheduler(plan).run()

    result = what_if(plan, "A", 50)
    assert result["old_makespan"] == 30
    assert result["new_makespan"] == 70
    assert result["delta"] == 40
    assert result["old_duration"] == 10
    assert result["new_duration"] == 50
    assert a.duration == 10   # original unchanged


def test_what_if_shrinks_makespan():
    a = make_event("A", 50, deadline_min=100)
    b = make_event("B", 20, deps=[a], deadline_min=100)
    plan = Plan([a, b], ORIGIN)
    CPMScheduler(plan).run()

    result = what_if(plan, "A", 10)
    assert result["delta"] == -40
    assert a.duration == 50


def test_what_if_no_change():
    a = make_event("A", 10, deadline_min=100)
    plan = Plan([a], ORIGIN)
    result = what_if(plan, "A", 10)
    assert result["delta"] == 0


def test_what_if_unknown_eid():
    plan = Plan([make_event("A", 10)], ORIGIN)
    with pytest.raises(KeyError):
        what_if(plan, "GHOST", 5)


def test_what_if_negative_duration():
    plan = Plan([make_event("A", 10)], ORIGIN)
    with pytest.raises(ValueError):
        what_if(plan, "A", -1)


# ---------- project-wide deadline ----------
def test_project_ddl_marks_tasks_and_project_overdue():
    a = make_event("A", dur=120, deadline_min=180)
    plan, result = scheduled([a])

    violations = deadline_violations(plan, dt(60))
    assert len(violations) == 1
    assert violations[0]["eid"] == "A"
    assert violations[0]["deadline"] == 60
    assert violations[0]["task_deadline"] == 180
    assert violations[0]["deadline_source"] == "project"
    assert violations[0]["late_minutes"] == 60

    report = feasibility_report(plan, result, dt(60))
    assert report.overdue_count == 1
    assert report.project_overdue is True
    assert report.project_late_minutes == 60
    assert report.project_late_human == "1h"
    assert report.is_feasible is False
    assert report.project_finish == dt(120).isoformat()

    rows = gantt_data(plan, dt(60))
    assert rows[0]["status"] == "overdue"


def test_project_ddl_after_finish_is_feasible():
    a = make_event("A", dur=120, deadline_min=300)
    plan, result = scheduled([a])
    report = feasibility_report(plan, result, dt(300))
    assert report.project_overdue is False
    assert report.overdue_count == 0
    assert report.is_feasible is True
