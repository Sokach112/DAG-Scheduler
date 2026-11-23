# tests/test_parallel.py
import datetime
import time
import pytest
from zoneinfo import ZoneInfo
from dag_scheduler import Event, Plan, CPMScheduler
from dag_scheduler.parallel import ParallelScheduler


TZ = ZoneInfo("Asia/Shanghai")
ORIGIN = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=TZ)


def dt(minutes: int) -> datetime.datetime:
    return ORIGIN + datetime.timedelta(minutes=minutes)


def make_event(eid, dur=10, priority=0, start_min=0, deadline_min=10_000,
               deps=None, capable_workers=None) -> Event:
    return Event(
        eid=eid, description=eid, duration=dur, priority=priority,
        start=dt(start_min), deadline=dt(deadline_min),
        dependencies=deps or [],
        capable_workers=capable_workers,
    )


def scheduled(events, workers, priority_key=None, worker_ids=None):
    """Build a Plan, run CPM, then run ParallelScheduler."""
    plan = Plan(events, ORIGIN)
    CPMScheduler(plan).run()
    return ParallelScheduler(
        plan, workers, priority_key, worker_ids=worker_ids).run()


# ---------- basic ----------
def test_empty_plan():
    res = scheduled([], workers=1)
    assert res.makespan == 0
    assert res.start == {}
    assert res.end == {}
    assert res.assignments == {}


def test_single_task():
    a = make_event("A", 30)
    res = scheduled([a], workers=1)
    assert res.start["A"] == 0
    assert res.end["A"] == 30
    assert res.makespan == 30
    assert res.assignments["A"] == 0


def test_workers_zero_raises():
    plan = Plan([make_event("A", 10)], ORIGIN)
    with pytest.raises(ValueError, match="workers"):
        ParallelScheduler(plan, workers=0)


# ---------- serial (workers=1) ----------
def test_serial_chain():
    a = make_event("A", 10)
    b = make_event("B", 20, deps=[a])
    c = make_event("C", 15, deps=[b])
    res = scheduled([a, b, c], workers=1)

    assert res.start["A"] == 0 and res.end["A"] == 10
    assert res.start["B"] == 10 and res.end["B"] == 30
    assert res.start["C"] == 30 and res.end["C"] == 45
    assert res.makespan == 45


def test_serial_parallel_roots_queue():
    """Two independent roots with workers=1 must queue."""
    a = make_event("A", 10)
    b = make_event("B", 20)
    res = scheduled([a, b], workers=1)

    # One runs, the other waits; total = sum of durations
    assert res.makespan == 30
    # Both are on worker 0
    assert res.assignments["A"] == 0
    assert res.assignments["B"] == 0
    # No overlap
    assert res.end["A"] <= res.start["B"] or res.end["B"] <= res.start["A"]


# ---------- parallel ----------
def test_parallel_roots_workers_2():
    a = make_event("A", 10)
    b = make_event("B", 20)
    res = scheduled([a, b], workers=2)

    assert res.start["A"] == 0
    assert res.start["B"] == 0
    assert res.makespan == 20
    assert {res.assignments["A"], res.assignments["B"]} == {0, 1}


def test_diamond_workers_1():
    """A -> (B, C) -> D, workers=1 forces B and C to serialize."""
    a = make_event("A", 10)
    b = make_event("B", 30, deps=[a])
    c = make_event("C", 30, deps=[a])
    d = make_event("D", 5, deps=[b, c])
    res = scheduled([a, b, c, d], workers=1)

    # Serial: A(10) + B or C(30) + the other(30) + D(5) = 75
    assert res.makespan == 75
    # D starts only after both B and C finish
    assert res.start["D"] >= res.end["B"]
    assert res.start["D"] >= res.end["C"]


def test_diamond_workers_2():
    """Same diamond with 2 workers runs B and C in parallel."""
    a = make_event("A", 10)
    b = make_event("B", 30, deps=[a])
    c = make_event("C", 30, deps=[a])
    d = make_event("D", 5, deps=[b, c])
    res = scheduled([a, b, c, d], workers=2)

    # A(10) + max(B, C)(30) + D(5) = 45
    assert res.makespan == 45
    assert res.start["B"] == 10
    assert res.start["C"] == 10


# ---------- resource lower bound ----------
def test_workers_ge_max_concurrency_matches_cpm():
    """With enough workers, resource schedule should match CPM makespan."""
    a = make_event("A", 10)
    b = make_event("B", 30)
    c = make_event("C", 20)
    d = make_event("D", 5, deps=[a, b])
    plan = Plan([a, b, c, d], ORIGIN)
    cpm = CPMScheduler(plan).run()
    res = ParallelScheduler(plan, workers=cpm.max_concurrency).run()

    assert res.makespan == cpm.makespan


def test_makespan_never_below_cpm():
    """Resource constraints can only delay, never accelerate."""
    # Rebuild cleanly
    a = make_event("A", 10)
    b = make_event("B", 20)
    c = make_event("C", 15)
    d = make_event("D", 5, deps=[a, b])
    events = [a, b, c, d]
    plan = Plan(events, ORIGIN)
    cpm = CPMScheduler(plan).run()
    res = ParallelScheduler(plan, workers=1).run()
    assert res.makespan >= cpm.makespan


# ---------- zero-duration: the "deadlock" rebuttal ----------
def test_zero_duration_chain_terminates():
    """4 zero-duration tasks in a chain must terminate quickly.

    If the scheduler looped forever on clock=0 milestones, this test
    would hang. The loop terminates because each task is consumed
    exactly once; clock not advancing is irrelevant to termination.
    """
    a = make_event("A", 0)
    b = make_event("B", 0, deps=[a])
    c = make_event("C", 0, deps=[b])
    d = make_event("D", 0, deps=[c])
    res = scheduled([a, b, c, d], workers=1)

    assert res.start == {"A": 0, "B": 0, "C": 0, "D": 0}
    assert res.end == {"A": 0, "B": 0, "C": 0, "D": 0}
    assert res.makespan == 0


def test_zero_duration_then_real_task():
    """Zero-duration chain doesn't advance clock; the real task after it does."""
    a = make_event("A", 5)
    b = make_event("B", 0, deps=[a])
    c = make_event("C", 0, deps=[b])
    d = make_event("D", 10, deps=[c])
    res = scheduled([a, b, c, d], workers=1)

    assert res.end["A"] == 5
    assert res.start["B"] == 5 and res.end["B"] == 5
    assert res.start["C"] == 5 and res.end["C"] == 5
    assert res.start["D"] == 5 and res.end["D"] == 15
    assert res.makespan == 15


def test_many_zero_duration_tasks_finish_fast():
    """100 zero-duration tasks must finish in well under a second."""
    events = []
    prev = None
    for i in range(100):
        e = make_event(f"E{i:03d}", 0, deps=[prev] if prev else [])
        events.append(e)
        prev = e

    t0 = time.time()
    res = scheduled(events, workers=1)
    elapsed = time.time() - t0

    assert len(res.start) == 100
    assert res.makespan == 0
    assert elapsed < 1.0, f"took {elapsed:.2f}s, possible infinite loop"


# ---------- named workers / capabilities ----------
def test_named_workers_and_capabilities():
    events = [
        make_event("A", capable_workers=["alice"]),
        make_event("B", capable_workers=["alice"]),
    ]
    result = scheduled(
        events, workers=2, worker_ids=["alice", "bob"])
    assert result.assignments == {"A": "alice", "B": "alice"}
    assert result.makespan == 20
    assert result.workers == 2
    assert result.worker_ids == ["alice", "bob"]
    assert result.capability_fallbacks == []


def test_capability_can_use_second_worker():
    events = [
        make_event("A", capable_workers=["alice"]),
        make_event("B", capable_workers=["bob"]),
    ]
    result = scheduled(
        events, workers=2, worker_ids=["alice", "bob"])
    assert result.assignments == {"A": "alice", "B": "bob"}
    assert result.makespan == 10


def test_empty_capabilities_mean_all_workers():
    events = [make_event("A"), make_event("B")]
    result = scheduled(events, workers=2)
    assert set(result.assignments.values()) == {0, 1}
    assert result.capability_fallbacks == []


def test_capability_falls_back_when_no_active_worker_matches():
    events = [make_event("A", capable_workers=["ghost"])]
    result = scheduled(
        events, workers=2, worker_ids=["alice", "bob"])
    assert result.assignments["A"] in {"alice", "bob"}
    assert result.capability_fallbacks == ["A"]


def test_active_worker_match_prevents_fallback():
    events = [make_event("A", capable_workers=["bob", "ghost"])]
    result = scheduled(
        events, workers=2, worker_ids=["alice", "bob"])
    assert result.assignments == {"A": "bob"}
    assert result.capability_fallbacks == []


def test_load_balancing_uses_idle_worker():
    a = make_event("A")
    b = make_event("B")
    c = make_event("C", deps=[a, b])
    result = scheduled([a, b, c], workers=3)
    assert result.assignments["A"] == 0
    assert result.assignments["B"] == 1
    assert result.assignments["C"] == 2
    assert result.makespan == 20


def test_load_balancing_uses_idle_named_worker():
    a = make_event("A", dur=1440)
    b = make_event("B", dur=1440)
    c = make_event("C", dur=2880, deps=[a, b])
    result = scheduled(
        [a, b, c], workers=3,
        worker_ids=["alice", "bob", "carl"])
    assert result.assignments["A"] == "alice"
    assert result.assignments["B"] == "bob"
    assert result.assignments["C"] == "carl"


def test_duplicate_named_worker_ids_rejected():
    plan = Plan([make_event("A")], ORIGIN)
    CPMScheduler(plan).run()
    with pytest.raises(ValueError):
        ParallelScheduler(
            plan, workers=2, worker_ids=["alice", "alice"])
