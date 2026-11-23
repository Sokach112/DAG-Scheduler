import datetime
from typing import List, Dict
from .models import Event
from .helper import SchedulerHelper
from .work_calendar import WorkCalendar


class Plan:
    """Time coordinate system for a set of events.

    All CPM offsets (est/eft/lst/lft) are integer minutes relative to
    `origin`. `origin` must be timezone-aware; every event's start and
    deadline must be tz-aware, on/after origin, and on whole-minute
    boundaries from origin.
    """

    def __init__(self, events: List[Event], origin: datetime.datetime,
                 skip_weekends: bool = False,
                 holidays=None,
                 holiday_ranges=None,
                 default_holidays: bool = False):
        if origin.tzinfo is None:
            raise ValueError("origin must be timezone-aware")

        self.events = events
        self.origin = origin
        self.skip_weekends = skip_weekends
        self.holidays = list(holidays or [])
        self.holiday_ranges = list(holiday_ranges or [])
        self.default_holidays = default_holidays
        self.calendar = WorkCalendar(
            origin, skip_weekends=skip_weekends, holidays=holidays,
            holiday_ranges=holiday_ranges,
            default_holidays=default_holidays)
        # Validates eid uniqueness and dependency existence.
        self.index: Dict[str, Event] = SchedulerHelper.events_to_index(events)
        self._validate_times()


    # ---------- validation ----------
    def _validate_times(self) -> None:
        for e in self.events:
            if e.start.tzinfo is None:
                raise ValueError(f"{e.eid}: start is naive datetime")
            if e.deadline.tzinfo is None:
                raise ValueError(f"{e.eid}: deadline is naive datetime")
            if e.start < self.origin:
                raise ValueError(f"{e.eid}: start is before origin")
            if e.deadline < e.start:
                raise ValueError(f"{e.eid}: deadline is before start")
            # Enforce whole-minute offsets (also catches sub-minute precision).
            self._offset(e.start, f"{e.eid}.start")
            self._offset(e.deadline, f"{e.eid}.deadline")


    def _offset(self, dt: datetime.datetime, name: str) -> int:
        secs = (dt - self.origin).total_seconds()
        if secs % 60 != 0:
            raise ValueError(
                f"{name} is not a whole number of minutes from origin")
        return int(secs // 60)


    # ---------- conversion ----------
    def to_offset(self, dt: datetime.datetime) -> int:
        """Absolute datetime -> minutes from origin."""
        return self._offset(dt, "datetime")


    def to_datetime(self, offset: int) -> datetime.datetime:
        """Minutes from origin -> absolute datetime."""
        return self.origin + datetime.timedelta(minutes=offset)


    # ---------- convenience ----------
    def start_offset(self, e: Event) -> int:
        return self.to_offset(e.start)


    def deadline_offset(self, e: Event) -> int:
        return self.to_offset(e.deadline)


    def topo_order(self) -> List[str]:
        return SchedulerHelper.topo_order(self.events)
