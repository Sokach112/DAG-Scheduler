"""Critical Path Method over a Plan.

All offsets (est/eft/lst/lft/slack) are integer minutes relative to
Plan.origin. See Event docstring for semantics.

Leaf lft = deadline offset (per-event hard deadline). Negative slack is
allowed and means the task is already overdue. Makespan is defined as
max(eft) - min(est).
"""

from dataclasses import dataclass, field
from typing import List, Dict

from models import Event
from plan import Plan
from helper import SchedulerHelper


@dataclass
class CPMResult:
    """Snapshot of a CPM run. Events are references, not copies."""
    makespan: int
    max_concurrency: int
    critical_path: List[str]
    overdue: List[str]
    events: List[Event] = field(repr=False)


class CPMScheduler:
    """Forward/backward pass over a DAG of Events.

    Construction validates the DAG (topological order raises CycleError
    on cycles). Call run() to populate est/eft/lst/lft/slack on every
    Event and get a CPMResult.
    """

    def __init__(self, plan: Plan):
        self.plan = plan
        self.index: Dict[str, Event] = plan.index
        self.order: List[str] = plan.topo_order()
        # dep -> [successor eid], used by backward_pass
        self.adj: Dict[str, List[str]] = \
            SchedulerHelper.events_to_adjacency(plan.events)


    # ---------- passes ----------
    def forward_pass(self) -> None:
        """Compute est/eft in topological order."""
        for eid in self.order:
            e = self.index[eid]
            start_off = self.plan.start_offset(e)
            pred_efts = [self.index[dep.eid].eft for dep in e.dependencies]
            e.est = max(pred_efts + [start_off])
            e.eft = e.est + e.duration


    def backward_pass(self) -> None:
        """Compute lft/lst/slack in reverse topological order."""
        for eid in reversed(self.order):
            e = self.index[eid]
            dl_off = self.plan.deadline_offset(e)
            succ_lsts = [self.index[s].lst for s in self.adj.get(eid, [])]
            e.lft = min(succ_lsts + [dl_off])
            e.lst = e.lft - e.duration
            e.slack = e.lst - e.est

    def max_concurrency(self) -> int:
        """Max number of tasks active simultaneously on the CPM timeline.

        A task is active on [est, eft). Zero-duration milestones do not
        contribute (they occupy no interval). Requires forward_pass.
        """
        events = [e for e in self.plan.events if e.duration > 0]
        if not events:
            return 0

        # (time, delta): +1 at est, -1 at eft
        points = []
        for e in events:
            points.append((e.est, +1))
            points.append((e.eft, -1))
        points.sort()

        current = 0
        peak = 0
        for _, delta in points:
            current += delta
            peak = max(peak, current)
        return peak


    # ---------- run ----------
    def run(self) -> CPMResult:
        self.forward_pass()
        self.backward_pass()
        return CPMResult(
            makespan=self.makespan(),
            max_concurrency=self.max_concurrency(),
            critical_path=self.critical_path(),
            overdue=self.overdue(),
            events=self.plan.events,
        )


    # ---------- queries ----------
    def makespan(self) -> int:
        """max(eft) - min(est). Requires forward_pass to have run."""
        if not self.plan.events:
            return 0
        return (max(e.eft for e in self.plan.events)
                - min(e.est for e in self.plan.events))


    def critical_path(self) -> List[str]:
        """One connected critical chain (slack == 0 throughout).

        Starts at a critical root (no critical predecessor) and follows
        critical successors until a critical leaf. When multiple chains
        exist, picks the lexicographically smallest eid sequence, so the
        result is deterministic and independent of insertion order.

        Returns [] if no task has slack == 0 (all slack > 0 or all overdue).
        """
        critical = {eid for eid in self.order if self.index[eid].slack == 0}
        if not critical:
            return []

        def critical_preds(eid: str) -> List[str]:
            return [d.eid for d in self.index[eid].dependencies
                    if d.eid in critical]

        def critical_succs(eid: str) -> List[str]:
            return [s for s in self.adj.get(eid, []) if s in critical]

        roots = [eid for eid in critical if not critical_preds(eid)]
        if not roots:
            return []   # unreachable for a DAG, defensive

        chain = [min(roots)]
        while True:
            succs = critical_succs(chain[-1])
            if not succs:
                break
            chain.append(min(succs))
        return chain


    def critical_events(self) -> List[str]:
        """All eids with slack == 0, in topological order.

        This is the full set of critical tasks (may be multiple parallel
        chains). Use critical_path() for a single connected chain.
        """
        return [eid for eid in self.order if self.index[eid].slack == 0]


    def overdue(self) -> List[str]:
        """eids with slack < 0 (already past deadline)."""
        return [eid for eid in self.order if self.index[eid].slack < 0]


    def slack_of(self, eid: str) -> int:
        return self.index[eid].slack


    def is_critical(self, eid: str) -> bool:
        return self.index[eid].slack == 0


    # ---------- reset ----------
    def reset(self) -> None:
        """Clear all scheduling state so the Plan can be re-run."""
        for e in self.plan.events:
            e.est = e.eft = e.lst = e.lft = e.slack = 0
