"""
Core data models for the scheduler.

Time convention: all scheduling offsets (est/eft/lst/lft/slack) are
integer minutes relative to Plan.origin. Absolute times (start/deadline)
are timezone-aware datetimes.
"""

from __future__ import annotations
import datetime
from typing import List, Optional
from functools import total_ordering


@total_ordering
class Event:
    def __init__(self, 
                 eid: str, 
                 description: str, 
                 duration: int, 
                 priority: int,
                 start: datetime.datetime, 
                 deadline: datetime.datetime,
                 dependencies: Optional[List[Event]] = None, 
                 est: int = 0, 
                 eft: int = 0, 
                 lst: int = 0,
                 lft: int = 0, 
                 slack: int = 0):

        """A single scheduled task in a DAG-based plan.

        An Event represents a task with a fixed duration, a priority, a hard
        earliest start, a hard deadline, and zero or more dependencies. The
        scheduling state (est/eft/lst/lft/slack) is populated by CPMScheduler
        and is meaningless before a CPM run.

        Attributes:
            eid: Unique identifier within a plan. Used as the identity key
                for __eq__ and __hash__, and as the node name in adjacency
                lists and serialized output.
            description: Human-readable label.
            duration: Task duration in whole minutes. Must be >= 0.
            priority: Scheduling priority. Larger value = scheduled first
                (see __lt__).
            start: Earliest allowed start time. Hard constraint, must be
                timezone-aware and on or after the plan origin.
            deadline: Latest allowed finish time. Hard constraint, must be
                timezone-aware and on or after start.
            dependencies: Events that must finish before this one starts.
                The list is snapshotted at construction; mutating the
                original list afterwards does not affect this Event.
            est: Earliest start, in whole minutes relative to Plan.origin.
            eft: Earliest finish, in whole minutes relative to Plan.origin.
            lst: Latest start, in whole minutes relative to Plan.origin.
            lft: Latest finish, in whole minutes relative to Plan.origin.
            slack: lft - eft (== lst - est). Zero means critical path.

        Identity:
            Two Events are equal iff their eids match. __hash__ is derived
            from eid. Field values (description, duration, ...) do NOT
            participate in equality.

        Ordering:
            __lt__ compares (-priority, start, deadline, eid), so lower
            priority *number* sorts later (higher priority number first).
            This ordering is intended for ready-queue and heuristic
            selection, not for CPM computation.
        """

        self.eid = eid
        self.description = description
        self.duration = duration          # int, min
        self.priority = priority
        self.start = start                # datetime, the earliest starting time
        self.deadline = deadline          # datetime, the latest finish time
        self.dependencies = dependencies or []
        self.est = est                    # int, min
        self.eft = eft
        self.lst = lst
        self.lft = lft
        self.slack = slack


    def __repr__(self) -> str:
        return f"<Event {self.eid}: {self.description}, start: {self.start}, ddl: {self.deadline}>"


    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.eid == other.eid


    def __hash__(self) -> int:
        return hash(self.eid)


    def __lt__(self, other: object):
        """
        Compare logic: Element-wise (-priority, start, deadline, eid)
        """

        if not isinstance(other, Event):
            return NotImplemented

        self_cmp = (
            -self.priority, 
            self.start,
            self.deadline,
            self.eid
        )

        other_cmp = (
            -other.priority,
            other.start,
            other.deadline,
            other.eid
        )

        return self_cmp < other_cmp
