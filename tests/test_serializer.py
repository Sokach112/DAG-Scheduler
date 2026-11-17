import datetime
import pytest
import json
from zoneinfo import ZoneInfo
from dag_scheduler import Event, Plan, CPMScheduler
from dag_scheduler.serializer import (
    plan_to_dict, plan_from_dict,
    save_to_json, load_from_json,
    SerializationError,
)


TZ = ZoneInfo("Asia/Shanghai")
ORIGIN = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=TZ)


def dt(minutes):
    return ORIGIN + datetime.timedelta(minutes=minutes)


def make_event(eid, dur=10, priority=0, start_min=0, deadline_min=100, deps=None):
    return Event(
        eid=eid, description=eid, duration=dur, priority=priority,
        start=dt(start_min), deadline=dt(deadline_min),
        dependencies=deps or [],
    )


# ---------- round-trip ----------
def test_roundtrip_simple():
    a = make_event("A", 10)
    b = make_event("B", 20, deps=[a])
    plan = Plan([a, b], ORIGIN)

    restored = plan_from_dict(plan_to_dict(plan))

    assert restored.origin == plan.origin
    assert len(restored.events) == 2
    assert restored.index["A"].duration == 10
    assert restored.index["B"].dependencies[0].eid == "A"


def test_roundtrip_preserves_cpm():
    a = make_event("A", 10, deadline_min=45)
    b = make_event("B", 30, deps=[a], deadline_min=45)
    c = make_event("C", 30, deps=[a], deadline_min=45)
    d = make_event("D", 5, deps=[b, c], deadline_min=45)
    plan = Plan([a, b, c, d], ORIGIN)
    orig = CPMScheduler(plan).run()

    restored = plan_from_dict(plan_to_dict(plan))
    new = CPMScheduler(restored).run()

    assert new.makespan == orig.makespan
    assert new.critical_path == orig.critical_path
    assert new.overdue == orig.overdue


def test_roundtrip_unicode_description():
    a = make_event("A", 10)
    a.description = "Design Phase"
    plan = Plan([a], ORIGIN)

    restored = plan_from_dict(plan_to_dict(plan))
    assert restored.index["A"].description == "Design Phase"


def test_roundtrip_empty_plan():
    plan = Plan([], ORIGIN)
    restored = plan_from_dict(plan_to_dict(plan))
    assert restored.events == []


# ---------- file I/O ----------
def test_save_load_file(tmp_path):
    a = make_event("A", 10)
    b = make_event("B", 20, deps=[a])
    plan = Plan([a, b], ORIGIN)

    path = tmp_path / "plan.json"
    save_to_json(plan, str(path))
    restored = load_from_json(str(path))

    assert restored.origin == plan.origin
    assert len(restored.events) == 2


def test_saved_file_is_valid_json(tmp_path):
    a = make_event("A", 10)
    plan = Plan([a], ORIGIN)

    path = tmp_path / "plan.json"
    save_to_json(plan, str(path))
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["version"] == 1
    assert data["events"][0]["eid"] == "A"


# ---------- serialization errors ----------
def test_bad_version():
    data = {"version": 99, "origin": ORIGIN.isoformat(), "events": []}
    with pytest.raises(SerializationError, match="version"):
        plan_from_dict(data)


def test_missing_origin():
    with pytest.raises(SerializationError, match="origin"):
        plan_from_dict({"version": 1, "events": []})


def test_events_not_a_list():
    with pytest.raises(SerializationError, match="events"):
        plan_from_dict({"version": 1, "origin": ORIGIN.isoformat(),
                        "events": "not a list"})


def test_duplicate_eid():
    data = {
        "version": 1,
        "origin": ORIGIN.isoformat(),
        "events": [
            {"eid": "A", "description": "a", "duration": 10, "priority": 0,
             "start": dt(0).isoformat(), "deadline": dt(100).isoformat(),
             "dependencies": []},
            {"eid": "A", "description": "a2", "duration": 10, "priority": 0,
             "start": dt(0).isoformat(), "deadline": dt(100).isoformat(),
             "dependencies": []},
        ],
    }
    with pytest.raises(SerializationError, match="Duplicate"):
        plan_from_dict(data)


def test_unknown_dependency():
    data = {
        "version": 1,
        "origin": ORIGIN.isoformat(),
        "events": [
            {"eid": "A", "description": "a", "duration": 10, "priority": 0,
             "start": dt(0).isoformat(), "deadline": dt(100).isoformat(),
             "dependencies": ["GHOST"]},
        ],
    }
    with pytest.raises(SerializationError, match="GHOST"):
        plan_from_dict(data)


def test_missing_event_field():
    data = {
        "version": 1,
        "origin": ORIGIN.isoformat(),
        "events": [
            {"eid": "A", "duration": 10},   # missing description, etc.
        ],
    }
    with pytest.raises(SerializationError, match="Missing field"):
        plan_from_dict(data)


def test_bad_datetime_string():
    data = {
        "version": 1,
        "origin": "not-a-datetime",
        "events": [],
    }
    with pytest.raises(SerializationError, match="origin"):
        plan_from_dict(data)


# ---------- business validation passes through ----------
def test_business_validation_raises_value_error():
    """start before origin -> Plan raises ValueError, NOT wrapped."""
    data = {
        "version": 1,
        "origin": ORIGIN.isoformat(),
        "events": [
            {"eid": "A", "description": "a", "duration": 10, "priority": 0,
             "start": (ORIGIN - datetime.timedelta(minutes=5)).isoformat(),
             "deadline": dt(100).isoformat(),
             "dependencies": []},
        ],
    }
    with pytest.raises(ValueError, match="origin"):
        plan_from_dict(data)
