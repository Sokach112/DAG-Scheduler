"""In-memory plan store.

Single-process, not persisted. Restarting the server loses all plans.
For multi-worker deployment, use sticky sessions or replace with a
persistent backend.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dag_scheduler import Plan, CPMResult


@dataclass
class PlanSession:
    plan: Plan
    cpm: CPMResult
    created_at: datetime


_sessions: Dict[str, PlanSession] = {}


def put(plan_id: str, session: PlanSession) -> None:
    _sessions[plan_id] = session


def get(plan_id: str) -> Optional[PlanSession]:
    return _sessions.get(plan_id)


def delete(plan_id: str) -> None:
    _sessions.pop(plan_id, None)


def list_sessions() -> List[dict]:
    """Summary list for GET /plans."""
    return [
        {
            "plan_id": pid,
            "event_count": len(s.plan.events),
            "makespan": s.cpm.makespan,
            "created_at": s.created_at.isoformat(),
        }
        for pid, s in _sessions.items()
    ]
