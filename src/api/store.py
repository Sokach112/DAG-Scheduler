"""Persistence helpers for plans and projects.

Plans used by the stateless ``/plan`` endpoints live in memory (they are
short-lived calculation handles). Projects are persisted in SQLite and are
the durable unit saved by the web app.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from dag_scheduler import DEFAULT_ORIGIN, Plan, CPMResult, Project
from dag_scheduler.serializer import (
    events_to_dict,
    plan_from_dict,
)

from .db import ProjectModel, SessionLocal


@dataclass
class PlanSession:
    plan: Plan
    cpm: CPMResult
    created_at: datetime


_sessions: Dict[str, PlanSession] = {}


# ---------- transient plan sessions ----------
def put(plan_id: str, session: PlanSession) -> None:
    _sessions[plan_id] = session


def get(plan_id: str) -> Optional[PlanSession]:
    return _sessions.get(plan_id)


def delete(plan_id: str) -> None:
    _sessions.pop(plan_id, None)


def list_sessions() -> List[Dict[str, Any]]:
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


# ---------- persistent projects ----------
def _events_json(project: Project) -> str:
    """Serialize only the persisted event fields."""
    plan = project.to_plan()
    return json.dumps(events_to_dict(plan.events), ensure_ascii=False)


def _to_datetime(value: str | datetime | None) -> Optional[datetime]:
    """Accept ISO strings (current schema) and datetimes (old schema)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite DateTime columns return naive values; older rows may be naive."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=DEFAULT_ORIGIN.tzinfo)
    return value


def _row_to_project(row: ProjectModel) -> Project:
    origin = _aware(_to_datetime(row.origin)) or DEFAULT_ORIGIN
    ddl = _aware(_to_datetime(row.ddl))
    raw_events = json.loads(row.events_json or "[]")
    if raw_events:
        plan = plan_from_dict({
            "version": 1,
            "origin": origin.isoformat(),
            "events": raw_events,
        })
        events = plan.events
    else:
        events = []
    return Project(
        prid=row.prid,
        title=row.title or "Untitled Project",
        description=row.description or "",
        origin=origin,
        ddl=ddl,
        events=events,
    )


def create_project(project: Project) -> Project:
    """Insert a new project and return the persisted version."""
    with SessionLocal() as session:
        row = ProjectModel(
            prid=project.prid,
            title=project.title,
            description=project.description,
            origin=project.resolved_origin().isoformat(),
            ddl=project.ddl.isoformat() if project.ddl else None,
            events_json=_events_json(project),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_project(row)


def get_project(prid: str) -> Optional[Project]:
    with SessionLocal() as session:
        row = session.get(ProjectModel, prid)
        return _row_to_project(row) if row else None


def list_projects() -> List[Project]:
    with SessionLocal() as session:
        rows = session.query(ProjectModel).order_by(
            ProjectModel.updated_at.desc()).all()
        return [_row_to_project(row) for row in rows]


def update_project(project: Project) -> Optional[Project]:
    """Overwrite an existing project. Returns None if it does not exist."""
    with SessionLocal() as session:
        row = session.get(ProjectModel, project.prid)
        if row is None:
            return None
        row.title = project.title
        row.description = project.description
        row.origin = project.resolved_origin().isoformat()
        row.ddl = project.ddl.isoformat() if project.ddl else None
        row.events_json = _events_json(project)
        session.commit()
        session.refresh(row)
        return _row_to_project(row)


def delete_project(prid: str) -> bool:
    with SessionLocal() as session:
        row = session.get(ProjectModel, prid)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
