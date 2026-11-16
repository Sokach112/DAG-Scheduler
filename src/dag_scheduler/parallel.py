import heapq
from dataclasses import dataclass
from typing import List, Dict, Tuple, Callable, Any, Optional
from dag_scheduler import Event, Plan, SchedulerHelper
from collections import deque


@dataclass
class ResourceScheduleResult:
    """Result of a resource-constrained schedule.

    start/end are integer minutes relative to Plan.origin, same unit as
    CPM offsets. assignments maps eid -> worker id (0..workers-1).
    makespan = max(end) - min(start), matching CPM's definition.
    """
    makespan: int
    workers: int
    start: Dict[str, int]
    end: Dict[str, int]
    assignments: Dict[str, int]


class ParallelScheduler:
    def __init__(self, plan: Plan, workers: int,
                 priority_key: Optional[Callable[[Event], Any]] = None):
        if workers < 1:
            raise ValueError("workers must be >= 1")
        self.plan = plan
        self.workers = workers
        self.priority_key = priority_key or (lambda e: (-e.priority, e.slack, e.est, e.eid))
        self.index = plan.index
        self.order = plan.topo_order()
        self.adj = SchedulerHelper.events_to_adjacency(plan.events)


    def run(self) -> ResourceScheduleResult:
        start: Dict[str, int] = {}
        end: Dict[str, int] = {}
        assignment: Dict[str, int] = {}

        remaining_preds = {
            eid: len(self.index[eid].dependencies) for eid in self.order
        }
        ready = [(self.priority_key(self.index[eid]), eid) for eid in self.order if remaining_preds[eid] == 0]

        # running: min-heap of (end_time, eid, worker_id)
        running: List[Tuple[int, str, int]] = []
        free_workers: List[int] = list(range(self.workers))
        heapq.heapify(free_workers)
        heapq.heapify(ready)

        clock = 0

        while ready or running:
            # 1. Call ready tasks to fill free workers
            if ready and free_workers:
                while ready and free_workers:
                    _, eid = heapq.heappop(ready)
                    e = self.index[eid]
                    wid = heapq.heappop(free_workers)
                    s, f = max(clock, e.est), max(clock, e.est) + e.duration
                    start[eid], end[eid] = s, f
                    assignment[eid] = wid
                    heapq.heappush(running, (f, eid, wid))

            # 2. Complete the earlieast task
            if running:
                clock = running[0][0]
                while running and running[0][0] == clock:
                    _, eid, wid = heapq.heappop(running)
                    heapq.heappush(free_workers, wid)
                    for succ in self.adj.get(eid, []):
                        remaining_preds[succ] -= 1
                        if remaining_preds[succ] == 0:
                            heapq.heappush(ready, (self.priority_key(self.index[succ]), succ))

        makespan = (max(end.values()) - min(start.values())) if end else 0
        return ResourceScheduleResult(
            makespan=makespan,
            workers=self.workers,
            start=start,
            end=end,
            assignments=assignment,
        )
