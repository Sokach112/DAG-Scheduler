"""JSON serialization for Plan and Event.

Only inputs are serialized: origin, event fields, and dependency eids.
CPM outputs (est/eft/lst/lft/slack) are NOT persisted; run CPMScheduler
after loading to recompute them.

Format version 1:
{
  "version": 1,
  "origin": "<isoformat>",
  "events": [
    {"eid": ..., "description": ..., "duration": ...,
     "priority": ..., "start": "<isoformat>",
     "deadline": "<isoformat>", "dependencies": [eid, ...]}
  ]
}
"""

import datetime
import json
from typing import List, Dict, Any

from .models import Event
from .plan import Plan


FORMAT_VERSION = 1


class SerializationError(Exception):
    pass


def events_to_dict(events: List[Event]) -> List[Dict[str, Any]]:
    """Serialize only the input fields of a list of events."""
    return [
        {
            "eid": e.eid,
            "description": e.description,
            "details": e.details,
            "duration": e.duration,
            "priority": e.priority,
            "start": e.start.isoformat(),
            "deadline": e.deadline.isoformat(),
            "dependencies": [d.eid for d in e.dependencies],
            "capable_workers": list(e.capable_workers or []),
            "capable_workers_generic": list(
                e.capable_workers_generic or []),
        }
        for e in events
    ]


def plan_to_dict(plan: Plan) -> Dict[str, Any]:
    """Serialize a Plan to a plain dict (JSON-ready)."""
    return {
        "version": FORMAT_VERSION,
        "origin": plan.origin.isoformat(),
        "events": events_to_dict(plan.events),
    }


def plan_from_dict(data: Dict[str, Any]) -> Plan:
    """Deserialize a dict into a Plan.

    Raises SerializationError for format/structural problems, and
    ValueError for business validation failures surfaced by Plan's
    constructor (e.g. start before origin, deadline before start).
    """
    version = data.get("version")
    if version != FORMAT_VERSION:
        raise SerializationError(
            f"Unsupported format version: {version} (expected {FORMAT_VERSION})")

    try:
        origin = datetime.datetime.fromisoformat(data["origin"])
    except (KeyError, ValueError) as exc:
        raise SerializationError(f"Invalid origin: {exc}") from exc

    items = data.get("events")
    if not isinstance(items, list):
        raise SerializationError("'events' must be a list")

    # Pass 1: build events with empty dependencies
    index: Dict[str, Event] = {}
    for item in items:
        try:
            eid = item["eid"]
            if eid in index:
                raise SerializationError(f"Duplicate eid: {eid}")
            e = Event(
                eid=eid,
                description=item["description"],
                details=item.get("details", ""),
                duration=item["duration"],
                priority=item["priority"],
                start=datetime.datetime.fromisoformat(item["start"]),
                deadline=datetime.datetime.fromisoformat(item["deadline"]),
                dependencies=[],
                capable_workers=item.get("capable_workers", []),
                capable_workers_generic=item.get(
                    "capable_workers_generic", []),
            )
            index[eid] = e
        except KeyError as exc:
            raise SerializationError(f"Missing field: {exc}") from exc
        except ValueError as exc:
            # fromisoformat can raise ValueError on bad datetime strings
            raise SerializationError(f"Invalid datetime: {exc}") from exc

    # Pass 2: wire dependencies by eid
    for item in items:
        e = index[item["eid"]]
        dep_eids = item.get("dependencies", [])
        deps: List[Event] = []
        for dep_eid in dep_eids:
            if dep_eid not in index:
                raise SerializationError(
                    f"{e.eid} depends on unknown eid: {dep_eid}")
            deps.append(index[dep_eid])
        e.dependencies = deps

    return Plan(list(index.values()), origin)


def save_to_json(plan: Plan, path: str) -> None:
    """Write a Plan to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan_to_dict(plan), f, indent=2, ensure_ascii=False)


def load_from_json(path: str) -> Plan:
    """Read a Plan from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return plan_from_dict(data)
