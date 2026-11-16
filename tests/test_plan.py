import datetime
import pytest
from zoneinfo import ZoneInfo
from dag_scheduler import Event, Plan, DuplicateIDError

TZ = ZoneInfo("Asia/Shanghai")
ORIGIN = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=TZ)


def dt(minutes: int) -> datetime.datetime:
    return ORIGIN + datetime.timedelta(minutes=minutes)


def make_event(eid, dur=10, priority=0, start_min=0, deadline_min=100,
               deps=None) -> Event:
    return Event(
        eid=eid, description=eid, duration=dur, priority=priority,
        start=dt(start_min), deadline=dt(deadline_min),
        dependencies=deps or [],
    )


def test_plan_basic():
    a = make_event("A")
    b = make_event("B", deps=[a])
    plan = Plan([a, b], ORIGIN)

    assert plan.origin is ORIGIN
    assert plan.events == [a, b]
    assert plan.index == {"A": a, "B": b}


def test_offset_roundtrip():
    plan = Plan([], ORIGIN)
    for m in (0, 1, 60, 1440, 10000):
        assert plan.to_offset(dt(m)) == m
        assert plan.to_datetime(m) == dt(m)


def test_event_offsets():
    a = make_event("A", start_min=30, deadline_min=90)
    plan = Plan([a], ORIGIN)
    assert plan.start_offset(a) == 30
    assert plan.deadline_offset(a) == 90


def test_plan_topo_order():
    a = make_event("A")
    b = make_event("B", deps=[a])
    c = make_event("C", deps=[b])
    plan = Plan([a, b, c], ORIGIN)
    assert plan.topo_order() == ["A", "B", "C"]


def test_duplicate_eid():
    a1 = make_event("A")
    a2 = make_event("A")
    with pytest.raises(DuplicateIDError):
        Plan([a1, a2], ORIGIN)


def test_dependency_not_in_list():
    a = make_event("A")
    ghost = make_event("GHOST")
    b = make_event("B", deps=[ghost])
    with pytest.raises(ValueError, match="GHOST"):
        Plan([a, b], ORIGIN)


def test_cycle_not_raised_by_plan():
    a = make_event("A")
    b = make_event("B", deps=[a])
    a.dependencies = [b]
    plan = Plan([a, b], ORIGIN)
    with pytest.raises(Exception):
        plan.topo_order()


def test_naive_origin():
    naive = datetime.datetime(2026, 1, 1, 9, 0)
    with pytest.raises(ValueError, match="origin"):
        Plan([], naive)


def test_naive_start():
    a = make_event("A")
    a.start = datetime.datetime(2026, 1, 1, 9, 0)   # Remove tzinfo
    with pytest.raises(ValueError, match="naive"):
        Plan([a], ORIGIN)


def test_naive_deadline():
    a = make_event("A")
    a.deadline = datetime.datetime(2026, 1, 1, 10, 0)
    with pytest.raises(ValueError, match="naive"):
        Plan([a], ORIGIN)


def test_start_before_origin():
    a = make_event("A", start_min=-10)   # 早于 origin
    with pytest.raises(ValueError, match="before origin"):
        Plan([a], ORIGIN)


def test_deadline_before_start():
    a = make_event("A", start_min=50, deadline_min=20)
    with pytest.raises(ValueError, match="deadline.*before.*start"):
        Plan([a], ORIGIN)


def test_non_whole_minute_start():
    a = make_event("A")
    a.start = ORIGIN + datetime.timedelta(seconds=90)   # 1m 30s
    with pytest.raises(ValueError, match="whole number of minutes"):
        Plan([a], ORIGIN)


def test_non_whole_minute_deadline():
    a = make_event("A")
    a.deadline = ORIGIN + datetime.timedelta(minutes=10, microseconds=1)
    with pytest.raises(ValueError, match="whole number of minutes"):
        Plan([a], ORIGIN)


def test_microsecond_only():
    a = make_event("A")
    a.deadline = ORIGIN + datetime.timedelta(minutes=10, microseconds=1)
    with pytest.raises(ValueError):
        Plan([a], ORIGIN)


def test_start_equals_origin():
    a = make_event("A", start_min=0)
    plan = Plan([a], ORIGIN)
    assert plan.start_offset(a) == 0


def test_zero_duration_ok():
    m = make_event("M", dur=0)
    plan = Plan([m], ORIGIN)
    assert plan.index["M"] is m


def test_zero_window():
    a = make_event("A", start_min=10, deadline_min=10)
    plan = Plan([a], ORIGIN)
    assert plan.start_offset(a) == plan.deadline_offset(a) == 10


def test_mixed_timezones():
    utc_start = datetime.datetime(
        2026, 1, 1, 1, 30, tzinfo=datetime.timezone.utc)
    a = make_event("A")
    a.start = utc_start
    plan = Plan([a], ORIGIN)
    assert plan.start_offset(a) == 30
