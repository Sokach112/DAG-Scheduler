from typing import List, Dict, Optional
from functools import total_ordering
import datetime


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


    def __eq__(self, other: Event) -> bool:
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
