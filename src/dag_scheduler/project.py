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
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from .models import Event
from .worker import Worker
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
        ddl: Optional project-wide deadline. Evaluated as a soft warning or
            hard infeasibility depending on ``deadline_mode``.
        events: The project's events. None is treated as an empty list.
        report: Optional cached feasibility report. Derived data, not
            persisted; populated by the API when a project is returned.
        workers: Named team roster. Task capabilities reference worker ids.
        worker_mode: Per-project mode: ``infinite``, ``1`` (single), or
            ``custom``.
        worker_count: Generic worker count used when no named roster exists.
        single_worker_id: Named worker selected in Single mode.
        active_worker_ids: Named workers active in Team mode.
        capability_mode: ``fallback`` (assign anyway) or ``strict``
            (reject a schedule that cannot honour capabilities).
        deadline_mode: ``soft`` (warn when ddl is missed) or ``hard``
            (the project is infeasible when the schedule misses ddl).
        skip_weekends: When true, scheduling skips Saturday/Sunday and
            dates listed in ``holidays`` (YYYY-MM-DD).
        holidays: Legacy single holiday dates in the project timezone.
        holiday_ranges: Holiday periods ``{"start": "YYYY-MM-DD",
            "end": "YYYY-MM-DD"}`` in the project timezone.
        default_holidays: Use the bundled statutory calendar in addition to
            custom periods.
        timezone_mode: ``iana`` for a named zone with DST, or ``fixed`` for
            a fixed UTC offset.
        timezone: IANA zone name used in ``iana`` mode.
        utc_offset_minutes: Offset from UTC used in ``fixed`` mode.
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
    workers: Optional[List[Worker]] = None
    worker_mode: str = "infinite"
    worker_count: int = 2
    single_worker_id: Optional[str] = None
    active_worker_ids: Optional[List[str]] = None
    capability_mode: str = "fallback"
    deadline_mode: str = "soft"
    skip_weekends: bool = False
    holidays: Optional[List[str]] = None
    holiday_ranges: Optional[List[Dict[str, str]]] = None
    default_holidays: bool = False
    timezone_mode: str = "iana"
    timezone: str = "Asia/Shanghai"
    utc_offset_minutes: Optional[int] = None

    def resolved_origin(self) -> datetime.datetime:
        """Return the effective origin, keeping every event on/after it."""
        if self.origin is not None:
            return self.origin
        if self.events:
            return min(e.start for e in self.events)
        return DEFAULT_ORIGIN

    def resolved_timezone(self) -> datetime.tzinfo:
        if self.timezone_mode == "fixed":
            return datetime.timezone(
                datetime.timedelta(minutes=self.utc_offset_minutes or 0))
        try:
            return ZoneInfo(self.timezone or "Asia/Shanghai")
        except Exception:
            return DEFAULT_ORIGIN.tzinfo

    def to_plan(self) -> Plan:
        """Build a Plan for this project. Dependency wiring is preserved."""
        return Plan(
            list(self.events or []), self.resolved_origin(),
            skip_weekends=self.skip_weekends,
            holidays=self.holidays,
            holiday_ranges=self.holiday_ranges,
            default_holidays=self.default_holidays,
            timezone=self.resolved_timezone(),
        )
