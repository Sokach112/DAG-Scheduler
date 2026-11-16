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


    # ---------- run ----------
    def run(self) -> CPMResult:
        self.forward_pass()
        self.backward_pass()
        return CPMResult(
            makespan=self.makespan(),
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
        """eids with slack == 0, in topological order."""
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
