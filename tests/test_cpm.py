import pytest
import datetime
from zoneinfo import ZoneInfo
from models import Event
from plan import Plan
from cpm import CPMScheduler
from helper import CycleError
from typing import List, Optional


TZ = ZoneInfo("Asia/Shanghai")
ORIGIN = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=TZ)


def dt(minutes: int) -> datetime.datetime:
    """ORIGIN + minutes"""
    return ORIGIN + datetime.timedelta(minutes=minutes)


def make_event(eid: str,
               dur: int, 
               priority: int = 0, 
               start_min: int = 0, 
               deadline_min: int = 10000,
               deps: Optional[List[Event]] = None) -> Event:
    return Event(
        eid=eid,
        description=eid,
        duration=dur,
        priority=priority,
        start=dt(start_min),
        deadline=dt(deadline_min),
        dependencies=deps or [],
    )


class Case:
    def __init__(self, name, fn):
        self.name = name
        self.fn = fn


def run_cases(cases):
    print("======= CPM tests started =======")
    passed = 0
    for c in cases:
        try:
            c.fn()
            passed += 1
            print(f"[PASS] {c.name}")
        except AssertionError as e:
            print(f"[FAIL] {c.name}: {e}")
        except Exception as e:
            print(f"[ERROR] {c.name}: {repr(e)}")
    print(f"======= {passed}/{len(cases)} passed =======")


def test_linear_chain_all_critical():
    a = make_event("A", 30, start_min=0)
    b = make_event("B", 20, deps=[a])
    c = make_event("C", 10, deps=[b])
    # deadline = cpl -> All slack == 0
    a.deadline = dt(60)
    b.deadline = dt(60)
    c.deadline = dt(60)

    plan = Plan([a, b, c], ORIGIN)
    res = CPMScheduler(plan).run()

    assert a.est == 0 and a.eft == 30
    assert b.est == 30 and b.eft == 50
    assert c.est == 50 and c.eft == 60
    assert res.makespan == 60
    assert res.critical_path == ["A", "B", "C"]
    assert res.overdue == []


def test_diamond_long_branch_critical():
    a = make_event("A", 10)
    b = make_event("B", 30, deps=[a])    # Long
    c = make_event("C", 10, deps=[a])    # Short
    d = make_event("D", 5,  deps=[b, c])
    for e in (a, b, c, d):
        e.deadline = dt(45)              # A10 + B30 + D5 = 45

    plan = Plan([a, b, c, d], ORIGIN)
    res = CPMScheduler(plan).run()

    assert a.est == 0 and a.eft == 10
    assert b.est == 10 and b.eft == 40
    assert c.est == 10 and c.eft == 20
    assert d.est == 40 and d.eft == 45
    assert a.slack == 0 and b.slack == 0 and d.slack == 0
    assert c.slack == 20
    assert set(res.critical_path) == {"A", "B", "D"}


def test_all_slack_no_critical_path():
    a = make_event("A", 10, deadline_min=100)
    b = make_event("B", 10, deps=[a], deadline_min=100)
    plan = Plan([a, b], ORIGIN)
    res = CPMScheduler(plan).run()

    assert a.slack == 80 and b.slack == 80
    assert res.critical_path == []
    assert res.overdue == []


def test_overdue_negative_slack():
    a = make_event("A", 50, deadline_min=30)
    plan = Plan([a], ORIGIN)
    res = CPMScheduler(plan).run()

    assert a.est == 0 and a.eft == 50
    assert a.lft == 30 and a.lst == -20
    assert a.slack == -20
    assert res.overdue == ["A"]
    assert res.critical_path == []


def test_milestone_zero_duration():
    a = make_event("A", 30, deadline_min=40)
    m = make_event("M", 0, deps=[a], deadline_min=40)
    b = make_event("B", 10, deps=[m], deadline_min=40)

    plan = Plan([a, m, b], ORIGIN)
    res = CPMScheduler(plan).run()

    assert m.est == 30 and m.eft == 30
    assert b.est == 30 and b.eft == 40
    assert res.critical_path == ["A", "M", "B"]


def test_start_hard_constraint():
    a = make_event("A", 10, deadline_min=100)
    b = make_event("B", 10, deps=[a], start_min=50, deadline_min=100)
    plan = Plan([a, b], ORIGIN)
    _ = CPMScheduler(plan).run()

    assert b.est == 50
    assert b.eft == 60


def test_deadline_hard_constraint_in_backward():
    a = make_event("A", 10, deadline_min=20)
    b = make_event("B", 10, deps=[a], deadline_min=100)
    plan = Plan([a, b], ORIGIN)
    _ = CPMScheduler(plan).run()

    assert b.est == 10 and b.eft == 20
    assert b.lft == 100 and b.lst == 90
    assert a.lft == 20
    assert a.lst == 10


def test_empty_plan():
    plan = Plan([], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.makespan == 0
    assert res.critical_path == []
    assert res.overdue == []


def test_cycle_raises_on_construction():
    a = make_event("A", 10)
    b = make_event("B", 10, deps=[a])
    a.dependencies = [b]
    plan = Plan([a, b], ORIGIN)
    with pytest.raises(CycleError):
        CPMScheduler(plan)


def test_makespan_uses_min_est():
    a = make_event("A", 10, start_min=100, deadline_min=200)
    b = make_event("B", 10, deps=[a], deadline_min=200)
    plan = Plan([a, b], ORIGIN)
    res = CPMScheduler(plan).run()

    assert a.est == 100 and b.eft == 120
    assert res.makespan == 20


def test_multiple_roots():
    a = make_event("A", 30, deadline_min=40)
    b = make_event("B", 20, deadline_min=40)
    c = make_event("C", 10, deps=[a, b], deadline_min=40)
    plan = Plan([a, b, c], ORIGIN)
    res = CPMScheduler(plan).run()

    assert c.est == 30
    assert c.eft == 40
    assert a.slack == 0 and b.slack == 10
    assert res.critical_path == ["A", "C"]


def test_max_concurrency_linear():
    a = make_event("A", 30)
    b = make_event("B", 20, deps=[a])
    plan = Plan([a, b], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.max_concurrency == 1


def test_max_concurrency_parallel_roots():
    a = make_event("A", 30)
    b = make_event("B", 20)
    plan = Plan([a, b], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.max_concurrency == 2


def test_max_concurrency_half_open_interval():
    # A ends at 30, B starts at 30. Half-open [est, eft) → no overlap.
    a = make_event("A", 30)
    b = make_event("B", 20, deps=[a])
    plan = Plan([a, b], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.max_concurrency == 1


def test_max_concurrency_diamond():
    a = make_event("A", 10)
    b = make_event("B", 30, deps=[a])
    c = make_event("C", 30, deps=[a])
    d = make_event("D", 5, deps=[b, c])
    plan = Plan([a, b, c, d], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.max_concurrency == 2   # B and C overlap


def test_max_concurrency_all_milestones():
    m1 = make_event("M1", 0)
    m2 = make_event("M2", 0)
    plan = Plan([m1, m2], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.max_concurrency == 0


def test_max_concurrency_staggered():
    # A [0,10), B [5,15), C [8,12) → at t=8, all three active
    a = make_event("A", 10, start_min=0)
    b = make_event("B", 10, start_min=5)
    c = make_event("C", 4,  start_min=8)
    plan = Plan([a, b, c], ORIGIN)
    res = CPMScheduler(plan).run()
    assert res.max_concurrency == 3
