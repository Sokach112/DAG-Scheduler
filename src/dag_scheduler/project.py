"""Project: a persistent container for events and project-level metadata.

A Project is the unit the web app saves. It owns the event list plus the
project-level time frame:

    origin  coordinate origin for all CPM offsets (auto-resolved when None)
    ddl     optional project-wide deadline, intended for global overdue checks

CPM outputs and the feasibility report are derived data: they are computed
on demand and returned to clients, but never persisted.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .models import Event
from .plan import Plan


DEFAULT_ORIGIN = datetime.datetime(
    2026, 1, 1, 9, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8))
)


@dataclass
class Project:
    """A named collection of events with a shared time coordinate system.

    Attributes:
        prid: Stable project identifier (string, unique).
        title: Human-readable project name.
        wsid: Owning workspace id. None means "assign the default workspace"
            on first persistence.
        description: Free-form project notes.
        origin: Coordinate origin. If None, the earliest event start (or
            DEFAULT_ORIGIN for an empty project) is used.
        ddl: Optional project-wide deadline. Reserved for global overdue
            evaluation; not used by the scheduler yet.
        events: The project's events. None is treated as an empty list.
        report: Optional cached feasibility report. Derived data, not
            persisted; populated by the API when a project is returned.
    """

    prid: str
    title: str
    wsid: Optional[str] = None
    description: str = ""
    origin: Optional[datetime.datetime] = None
    ddl: Optional[datetime.datetime] = None
    events: Optional[List[Event]] = None
    report: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    def resolved_origin(self) -> datetime.datetime:
        """Return the effective origin, keeping every event on/after it."""
        if self.origin is not None:
            return self.origin
        if self.events:
            return min(e.start for e in self.events)
        return DEFAULT_ORIGIN

    def to_plan(self) -> Plan:
        """Build a Plan for this project. Dependency wiring is preserved."""
        return Plan(list(self.events or []), self.resolved_origin())
