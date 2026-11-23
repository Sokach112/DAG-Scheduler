"""Working-day calendar for project scheduling.

A day is either fully working or fully non-working; this intentionally models
"skip weekends and holidays" without introducing shifts or partial working
hours yet.
"""

from __future__ import annotations

import datetime
from typing import Iterable, List, Optional, Set

from .default_holidays import all_default_datasets


class WorkCalendar:
    def __init__(self, origin: datetime.datetime,
                 skip_weekends: bool = False,
                 holidays: Optional[Iterable[str]] = None,
                 holiday_ranges: Optional[Iterable[dict]] = None,
                 default_holidays: bool = False,
                 timezone=None):
        if origin.tzinfo is None:
            raise ValueError("calendar origin must be timezone-aware")
        self.origin = origin
        self.timezone = timezone or origin.tzinfo
        self.skip_weekends = skip_weekends
        self.default_holidays = default_holidays

        self.custom_holidays: Set[datetime.date] = set()
        self.default_holiday_dates: Set[datetime.date] = set()
        self.extra_workdays: Set[datetime.date] = set()

        def add_range(start: str, end: str) -> None:
            try:
                start_day = datetime.date.fromisoformat(start)
                end_day = datetime.date.fromisoformat(end)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid holiday range: {start!r} - {end!r}") from exc
            if end_day < start_day:
                raise ValueError(f"holiday range ends before it starts: {start} - {end}")
            day = start_day
            while day <= end_day:
                self.custom_holidays.add(day)
                day += datetime.timedelta(days=1)

        for value in holidays or []:
            add_range(value, value)
        for item in holiday_ranges or []:
            add_range(item["start"], item["end"])

        if default_holidays:
            for dataset in all_default_datasets():
                for item in dataset.get("holidays", []):
                    day = datetime.date.fromisoformat(item["start"])
                    last = datetime.date.fromisoformat(item["end"])
                    while day <= last:
                        self.default_holiday_dates.add(day)
                        day += datetime.timedelta(days=1)
                for value in dataset.get("makeup_workdays", []):
                    self.extra_workdays.add(
                        datetime.date.fromisoformat(value))

    # ---------- date helpers ----------
    def _local(self, offset: int) -> datetime.datetime:
        return (self.origin + datetime.timedelta(minutes=offset)).astimezone(
            self.timezone)

    def _linear_offset(self, dt: datetime.datetime) -> int:
        return int((dt - self.origin).total_seconds() // 60)

    def _date(self, offset: int) -> datetime.date:
        return self._local(offset).date()

    def _day_start(self, day: datetime.date) -> int:
        midnight = datetime.datetime.combine(
            day, datetime.time.min, tzinfo=self.timezone)
        return self._linear_offset(midnight)

    def is_working_date(self, day: datetime.date) -> bool:
        if not self.skip_weekends:
            return True
        if day in self.custom_holidays:
            return False
        if self.default_holidays and day in self.extra_workdays:
            return True
        if self.default_holidays and day in self.default_holiday_dates:
            return False
        return day.weekday() < 5

    def _next_working_date(self, day: datetime.date) -> datetime.date:
        while not self.is_working_date(day):
            day += datetime.timedelta(days=1)
        return day

    def _previous_working_date(self, day: datetime.date) -> datetime.date:
        while not self.is_working_date(day):
            day -= datetime.timedelta(days=1)
        return day

    # ---------- conversions ----------
    def ceil_to_working(self, offset: int) -> int:
        """First working instant at/after offset, preserving time of day."""
        if not self.skip_weekends:
            return offset
        day = self._date(offset)
        if self.is_working_date(day):
            return offset
        time_of_day = offset - self._day_start(day)
        next_day = self._next_working_date(day + datetime.timedelta(days=1))
        return self._day_start(next_day) + time_of_day

    def floor_to_working(self, offset: int) -> int:
        """Latest working-day end at/before offset."""
        if not self.skip_weekends:
            return offset
        day = self._date(offset)
        if self.is_working_date(day):
            return offset
        previous = self._previous_working_date(
            day - datetime.timedelta(days=1))
        return self._day_start(previous + datetime.timedelta(days=1))

    def add_working(self, offset: int, duration: int) -> int:
        if not self.skip_weekends or duration <= 0:
            return self.ceil_to_working(offset) + max(0, duration)

        current = self.ceil_to_working(offset)
        remaining = duration
        day = self._date(current)
        while True:
            day_end = self._day_start(day + datetime.timedelta(days=1))
            available = day_end - current
            if remaining <= available:
                return current + remaining
            remaining -= available
            day = self._next_working_date(day + datetime.timedelta(days=1))
            current = self._day_start(day)

    def subtract_working(self, offset: int, duration: int) -> int:
        if not self.skip_weekends or duration <= 0:
            return self.floor_to_working(offset) - max(0, duration)

        current = self.floor_to_working(offset)
        remaining = duration
        day = self._date(current)
        if not self.is_working_date(day):
            previous = self._previous_working_date(
                day - datetime.timedelta(days=1))
            day = previous
            current = self._day_start(day + datetime.timedelta(days=1))
        elif current == self._day_start(day):
            previous = self._previous_working_date(
                day - datetime.timedelta(days=1))
            day = previous
            current = self._day_start(day + datetime.timedelta(days=1))

        while True:
            day_start = self._day_start(day)
            available = current - day_start
            if remaining <= available:
                return current - remaining
            remaining -= available
            day = self._previous_working_date(
                day - datetime.timedelta(days=1))
            current = self._day_start(day + datetime.timedelta(days=1))
