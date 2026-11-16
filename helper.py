from typing import List, Dict, Iterable, Callable, Optional, Any
from graphxlib import UnweightedGraph
from collections import defaultdict, deque
from models import Event
import datetime
import warnings


class CycleError(Exception):
    pass


class DuplicateIDError(Exception):
    pass


class EventFactory:
    """A baseline factory."""

    def __init__(self, prefix: str = "evt"):
        self.prefix = prefix
        self._counter = 0
        self._used: set = set()

    def __call__(self,
                 description: str,
                 duration: int,
                 priority: int,
                 start: datetime.datetime,
                 deadline: datetime.datetime,
                 dependencies: Optional[List[Event]] = None,
                 eid: Optional[str] = None) -> Event:
        if eid is None:
            while True:
                self._counter += 1
                eid = f"{self.prefix}-{self._counter:03d}"
                if eid not in self._used:
                    break
        self._used.add(eid)
        return Event(eid, description, duration, priority,
                     start, deadline, dependencies)


class SchedulerHelper:
    """Shared toolbox. All public APIs speak eid (str)."""

    # ---------- Event <-> id ----------
    @staticmethod
    def events_to_adjacency(events: List[Event]) -> Dict[str, List[str]]:
        """dep_id -> [eid]. Every event gets a key, even isolated ones."""
        graph: Dict[str, List[str]] = defaultdict(list)
        for e in events:
            graph[e.eid]  # ensure key exists
            for dep in e.dependencies:
                graph[dep.eid].append(e.eid)
        return dict(graph)

    @staticmethod
    def events_to_index(events: List[Event]) -> Dict[str, Event]:
        """eid -> Event. Validate uniqueness and dependency existence."""
        index: Dict[str, Event] = {}
        for e in events:
            if e.eid in index:
                raise DuplicateIDError(f"Duplicate eid: {e.eid}")
            index[e.eid] = e
        for e in events:
            for dep in e.dependencies:
                if dep.eid not in index:
                    raise ValueError(
                        f"{e.eid} depends on {dep.eid}, "
                        f"which is not in the event list")
        return index

    # ---------- Topology ----------
    @staticmethod
    def topo_order(events: List[Event]) -> List[str]:
        """Topological order of eids. Raise CycleError on cycle."""
        adj = SchedulerHelper.events_to_adjacency(events)
        if not adj:
            return []
        try:
            hierarchy = UnweightedGraph.topological_sort(adj)
        except ValueError as exc:
            raise CycleError("Deadlock detected.") from exc
        return sorted(hierarchy, key=lambda eid: hierarchy[eid])

    # ---------- Query ----------
    @staticmethod
    def upstream_dependencies(events: List[Event], eid: str) -> List[str]:
        """All transitive upstream dependencies of eid."""
        index = SchedulerHelper.events_to_index(events)
        if eid not in index:
            warnings.warn(f"{eid} not in event list", stacklevel=2)
            return []

        start = index[eid]
        upstreams: List[str] = []
        seen = {start}
        q = deque(start.dependencies)

        while q:
            e = q.popleft()
            if e in seen:
                continue
            seen.add(e)
            upstreams.append(e.eid)
            q.extend(e.dependencies)
        return upstreams

    @staticmethod
    def downstream_dependents(events: List[Event], eid: str) -> List[str]:
        """All transitive downstream dependents of eid."""
        index = SchedulerHelper.events_to_index(events)
        if eid not in index:
            warnings.warn(f"{eid} not in event list", stacklevel=2)
            return []

        adj = SchedulerHelper.events_to_adjacency(events)  # dep_id -> [id]
        result: List[str] = []
        seen = {eid}
        q = deque(adj.get(eid, []))

        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            result.append(cur)
            q.extend(adj.get(cur, []))
        return result

    @staticmethod
    def direct_successors(events: List[Event], eid: str) -> List[str]:
        """Immediate successors of eid."""
        return SchedulerHelper.events_to_adjacency(events).get(eid, [])

    # ---------- Sort ----------
    @staticmethod
    def sort_by_key(events: Iterable[Event],
                    key: Callable[[Event], Any]) -> List[Event]:
        """Unified sort."""
        return sorted(events, key=key)
