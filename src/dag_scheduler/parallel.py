import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from dag_scheduler import Event, Plan, SchedulerHelper


@dataclass
class ResourceScheduleResult:
    """Result of a resource-constrained schedule.

    start/end are integer minutes relative to Plan.origin, same unit as
    CPM offsets. assignments maps eid -> worker id.

    Worker ids are integers (0..workers-1) for the legacy numeric API, or
    stable string ids when the caller supplies a named worker roster.
    makespan = max(end) - min(start), matching CPM's definition.
    """
    makespan: int
    workers: int
    start: Dict[str, int]
    end: Dict[str, int]
    assignments: Dict[str, Any]
    worker_ids: List[Any] = field(default_factory=list)
    capability_fallbacks: List[str] = field(default_factory=list)


class ParallelScheduler:
    def __init__(self, plan: Plan, workers: int,
                 priority_key: Optional[Callable[[Event], Any]] = None,
                 worker_ids: Optional[List[Any]] = None,
                 capability_field: str = "capable_workers"):
        if worker_ids is None:
            if workers < 1:
                raise ValueError("workers must be >= 1")
            self.worker_ids: List[Any] = list(range(workers))
        else:
            self.worker_ids = list(worker_ids)
            if not self.worker_ids:
                raise ValueError("at least one worker is required")
            if len({str(wid) for wid in self.worker_ids}) != len(
                    self.worker_ids):
                raise ValueError("worker ids must be unique")
        self.workers = len(self.worker_ids)
        self.plan = plan
        self.priority_key = priority_key or (
            lambda e: (-e.priority, e.slack, e.est, e.eid))
        self.index = plan.index
        self.order = plan.topo_order()
        self.adj = SchedulerHelper.events_to_adjacency(plan.events)
        self._fallbacks: Set[str] = set()
        self.capability_field = capability_field

    def _eligible_workers(self, event: Event) -> List[Any]:
        """Active workers that can run this task.

        An empty capability list means every active worker. When a task lists
        only workers outside the active set, fall back to all active workers
        and record the eid; this guarantees a schedule while surfacing that a
        restriction could not be honoured.
        """
        capable = list(getattr(event, self.capability_field, []) or [])
        if not capable:
            return list(self.worker_ids)

        capable_set = set(capable)
        eligible = [wid for wid in self.worker_ids if wid in capable_set]
        if eligible:
            return eligible

        self._fallbacks.add(event.eid)
        return list(self.worker_ids)

    def run(self) -> ResourceScheduleResult:
        start: Dict[str, int] = {}
        end: Dict[str, int] = {}
        assignment: Dict[str, Any] = {}

        remaining_preds = {
            eid: len(self.index[eid].dependencies) for eid in self.order
        }
        ready = [
            (self.priority_key(self.index[eid]), eid)
            for eid in self.order if remaining_preds[eid] == 0
        ]
        heapq.heapify(ready)

        # running: min-heap of (end_time, eid, worker_id)
        running: List[Tuple[int, str, Any]] = []
        free: Set[Any] = set(self.worker_ids)
        worker_position = {
            wid: index for index, wid in enumerate(self.worker_ids)}
        # Total assigned work per worker. Picking the least-loaded capable
        # worker spreads tasks instead of always choosing the lowest index
        # (which left later workers idle while the first worker did everything).
        worker_load: Dict[Any, int] = {
            wid: 0 for wid in self.worker_ids}
        worker_tasks: Dict[Any, int] = {
            wid: 0 for wid in self.worker_ids}

        clock = 0

        while ready or running:
            # Assign as many ready tasks as possible to capable free workers.
            progressed = True
            while ready and free and progressed:
                progressed = False
                deferred: List[Tuple[Any, str]] = []
                while ready:
                    priority, eid = heapq.heappop(ready)
                    event = self.index[eid]
                    eligible = self._eligible_workers(event)
                    candidates = [wid for wid in eligible if wid in free]
                    if candidates:
                        wid = min(
                            candidates,
                            key=lambda item: (
                                worker_load[item],
                                worker_tasks[item],
                                worker_position[item]
                            ))
                        free.remove(wid)
                        worker_load[wid] += event.duration
                        worker_tasks[wid] += 1
                        scheduled_start = max(clock, event.est)
                        scheduled_end = scheduled_start + event.duration
                        start[eid] = scheduled_start
                        end[eid] = scheduled_end
                        assignment[eid] = wid
                        heapq.heappush(
                            running, (scheduled_end, eid, wid))
                        progressed = True
                        break
                    deferred.append((priority, eid))
                for item in deferred:
                    heapq.heappush(ready, item)

            if running:
                clock = running[0][0]
                while running and running[0][0] == clock:
                    _, eid, wid = heapq.heappop(running)
                    free.add(wid)
                    for succ in self.adj.get(eid, []):
                        remaining_preds[succ] -= 1
                        if remaining_preds[succ] == 0:
                            heapq.heappush(
                                ready,
                                (self.priority_key(self.index[succ]), succ))
            elif ready:
                # Defensive: every task falls back to all active workers, so
                # this should be unreachable unless there are no workers.
                raise ValueError("scheduling deadlock: no worker available")

        makespan = (max(end.values()) - min(start.values())) if end else 0
        return ResourceScheduleResult(
            makespan=makespan,
            workers=self.workers,
            start=start,
            end=end,
            assignments=assignment,
            worker_ids=list(self.worker_ids),
            capability_fallbacks=sorted(self._fallbacks),
        )
