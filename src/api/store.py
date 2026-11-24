"""Persistence helpers for plans and projects.

Plans used by the stateless ``/plan`` endpoints live in memory (they are
short-lived calculation handles). Projects are persisted in SQLite and are
the durable unit saved by the web app.
"""

import json
import uuid
import datetime as dt
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dag_scheduler import (
    DEFAULT_ORIGIN,
    CPMResult,
    Plan,
    Project,
    Worker,
    Workspace,
)
from dag_scheduler.serializer import (
    events_to_dict,
    plan_from_dict,
)

from sqlalchemy import update

from .db import (
    ProjectModel, ProjectRevisionModel, SessionLocal, WorkspaceModel,
)


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


# ---------- persistent workspaces ----------
def _row_to_workspace(row: WorkspaceModel) -> Workspace:
    return Workspace(
        wsid=row.wsid,
        name=row.name or "My Workspace",
        description=row.description or "",
        created_at=row.created_at,
    )


def create_workspace(workspace: Workspace) -> Workspace:
    """Insert a new workspace and return the persisted version."""
    with SessionLocal() as session:
        row = WorkspaceModel(
            wsid=workspace.wsid or uuid.uuid4().hex[:8],
            name=workspace.name or "My Workspace",
            description=workspace.description or "",
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_workspace(row)


def get_workspace(wsid: str) -> Optional[Workspace]:
    with SessionLocal() as session:
        row = session.get(WorkspaceModel, wsid)
        return _row_to_workspace(row) if row else None


def list_workspaces() -> List[Workspace]:
    with SessionLocal() as session:
        rows = session.query(WorkspaceModel).order_by(
            WorkspaceModel.created_at, WorkspaceModel.wsid).all()
        return [_row_to_workspace(row) for row in rows]


def update_workspace(workspace: Workspace) -> Optional[Workspace]:
    """Update name/description. Returns None if the workspace is missing."""
    with SessionLocal() as session:
        row = session.get(WorkspaceModel, workspace.wsid)
        if row is None:
            return None
        row.name = workspace.name or "My Workspace"
        row.description = workspace.description or ""
        session.commit()
        session.refresh(row)
        return _row_to_workspace(row)


def delete_workspace(wsid: str) -> bool:
    """Delete a workspace and all of its projects (ORM cascade)."""
    with SessionLocal() as session:
        row = session.get(WorkspaceModel, wsid)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def get_or_create_default_workspace() -> Workspace:
    """Return the oldest workspace, creating 'My Workspace' if none exist.

    Until the UI has a workspace picker, projects created without a wsid are
    attached to this workspace.
    """
    with SessionLocal() as session:
        row = session.query(WorkspaceModel).order_by(
            WorkspaceModel.created_at, WorkspaceModel.wsid).first()
        if row is None:
            row = WorkspaceModel(name="My Workspace", description="")
            session.add(row)
            session.commit()
            session.refresh(row)
        return _row_to_workspace(row)


# ---------- persistent projects ----------
def _events_json(project: Project) -> str:
    """Serialize only the persisted event fields."""
    plan = project.to_plan()
    return json.dumps(events_to_dict(plan.events), ensure_ascii=False)


def _workers_json(project: Project) -> str:
    return json.dumps([
        {"wid": worker.wid, "name": worker.name}
        for worker in (project.workers or [])
    ], ensure_ascii=False)


def _active_worker_ids_json(project: Project) -> str:
    return json.dumps(list(project.active_worker_ids or []),
                      ensure_ascii=False)


def _holidays_json(project: Project) -> str:
    return json.dumps(list(project.holidays or []), ensure_ascii=False)


def _holiday_ranges_json(project: Project) -> str:
    return json.dumps(
        list(project.holiday_ranges or []), ensure_ascii=False)


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
    raw_workers = json.loads(row.workers_json or "[]")
    workers = [
        Worker(wid=item["wid"], name=item["name"])
        for item in raw_workers
        if item.get("wid") and item.get("name")
    ]
    raw_active = json.loads(row.active_worker_ids_json or "[]")
    active_worker_ids = [
        item for item in raw_active if isinstance(item, str)]
    raw_holidays = json.loads(row.holidays_json or "[]")
    holidays = [item for item in raw_holidays if isinstance(item, str)]
    raw_ranges = json.loads(row.holiday_ranges_json or "[]")
    holiday_ranges = [
        item for item in raw_ranges
        if isinstance(item, dict) and item.get("start") and item.get("end")
    ]
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
        wsid=row.wsid,
        description=row.description or "",
        origin=origin,
        ddl=ddl,
        events=events,
        created_at=row.created_at,
        updated_at=row.updated_at,
        workers=workers,
        worker_mode=row.worker_mode or "infinite",
        worker_count=row.worker_count or 2,
        single_worker_id=row.single_worker_id,
        active_worker_ids=active_worker_ids,
        capability_mode=row.capability_mode or "fallback",
        deadline_mode=row.deadline_mode or "soft",
        skip_weekends=bool(row.skip_weekends),
        holidays=holidays,
        holiday_ranges=holiday_ranges,
        default_holidays=bool(row.default_holidays),
        timezone_mode=row.timezone_mode or "iana",
        timezone=row.timezone or "Asia/Shanghai",
        utc_offset_minutes=row.utc_offset_minutes,
        version=row.version or 1,
    )


def create_project(project: Project) -> Project:
    """Insert a new project and return the persisted version.

    A project without a workspace is attached to the default workspace so
    the existing single-project API keeps working before the workspace UI
    lands.
    """
    wsid = project.wsid or get_or_create_default_workspace().wsid
    project.wsid = wsid
    with SessionLocal() as session:
        row = ProjectModel(
            prid=project.prid,
            wsid=wsid,
            title=project.title,
            description=project.description,
            origin=project.resolved_origin().isoformat(),
            ddl=project.ddl.isoformat() if project.ddl else None,
            events_json=_events_json(project),
            workers_json=_workers_json(project),
            worker_mode=project.worker_mode,
            worker_count=project.worker_count,
            single_worker_id=project.single_worker_id,
            active_worker_ids_json=_active_worker_ids_json(project),
            capability_mode=project.capability_mode,
            deadline_mode=project.deadline_mode,
            skip_weekends=project.skip_weekends,
            holidays_json=_holidays_json(project),
            holiday_ranges_json=_holiday_ranges_json(project),
            default_holidays=project.default_holidays,
            timezone_mode=project.timezone_mode,
            timezone=project.timezone,
            utc_offset_minutes=project.utc_offset_minutes,
            version=1,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_project(row)


def get_project(prid: str) -> Optional[Project]:
    with SessionLocal() as session:
        row = session.get(ProjectModel, prid)
        return _row_to_project(row) if row else None


def list_projects(wsid: Optional[str] = None) -> List[Project]:
    """List projects, optionally restricted to one workspace."""
    with SessionLocal() as session:
        query = session.query(ProjectModel)
        if wsid is not None:
            query = query.filter(ProjectModel.wsid == wsid)
        rows = query.order_by(ProjectModel.updated_at.desc()).all()
        return [_row_to_project(row) for row in rows]


def update_project(project: Project, expected_version: int
                   ) -> Optional[Project]:
    """Atomically update a project if its version still matches.

    Returns None for a missing project or a stale version.
    """
    with SessionLocal() as session:
        stmt = (
            update(ProjectModel)
            .where(
                ProjectModel.prid == project.prid,
                ProjectModel.version == expected_version,
            )
            .values(
                wsid=project.wsid,
                title=project.title,
                description=project.description,
                origin=project.resolved_origin().isoformat(),
                ddl=project.ddl.isoformat() if project.ddl else None,
                events_json=_events_json(project),
                workers_json=_workers_json(project),
                worker_mode=project.worker_mode,
                worker_count=project.worker_count,
                single_worker_id=project.single_worker_id,
                active_worker_ids_json=_active_worker_ids_json(project),
                capability_mode=project.capability_mode,
                deadline_mode=project.deadline_mode,
                skip_weekends=project.skip_weekends,
                holidays_json=_holidays_json(project),
                holiday_ranges_json=_holiday_ranges_json(project),
                default_holidays=project.default_holidays,
                timezone_mode=project.timezone_mode,
                timezone=project.timezone,
                utc_offset_minutes=project.utc_offset_minutes,
                version=ProjectModel.version + 1,
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        result = session.execute(stmt)
        if result.rowcount == 0:
            session.rollback()
            return None
        session.commit()
        row = session.get(ProjectModel, project.prid)
        return _row_to_project(row) if row else None


def _snapshot_timezone(snapshot: Dict) -> datetime.tzinfo:
    mode = snapshot.get("timezone_mode", "iana")
    if mode == "fixed":
        return dt.timezone(dt.timedelta(
            minutes=snapshot.get("utc_offset_minutes") or 0))
    try:
        return ZoneInfo(snapshot.get("timezone") or "Asia/Shanghai")
    except Exception:
        return DEFAULT_ORIGIN.tzinfo


def _project_snapshot(project: Project) -> Dict:
    plan = project.to_plan()
    return {
        "prid": project.prid,
        "wsid": project.wsid,
        "title": project.title,
        "description": project.description,
        "origin": plan.origin.isoformat(),
        "ddl": project.ddl.isoformat() if project.ddl else None,
        "events": events_to_dict(plan.events),
        "workers": [
            {"wid": worker.wid, "name": worker.name}
            for worker in (project.workers or [])
        ],
        "worker_mode": project.worker_mode,
        "worker_count": project.worker_count,
        "single_worker_id": project.single_worker_id,
        "active_worker_ids": list(project.active_worker_ids or []),
        "capability_mode": project.capability_mode,
        "deadline_mode": project.deadline_mode,
        "timezone_mode": project.timezone_mode,
        "timezone": project.timezone,
        "utc_offset_minutes": project.utc_offset_minutes,
        "skip_weekends": project.skip_weekends,
        "holidays": list(project.holidays or []),
        "holiday_ranges": list(project.holiday_ranges or []),
        "default_holidays": project.default_holidays,
        "version": project.version,
    }


REVISION_LIMIT = 10


def project_export_payload(project: Project) -> Dict:
    """Portable project JSON (no IDs or saved versions)."""
    snapshot = _project_snapshot(project)
    for key in ("prid", "wsid", "version"):
        snapshot.pop(key, None)
    return {
        "format": "dag-scheduler-project",
        "schema_version": 1,
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project": snapshot,
    }


def record_revision(project: Project, label: Optional[str] = None) -> None:
    snapshot = _project_snapshot(project)
    with SessionLocal() as session:
        existing = session.query(ProjectRevisionModel).filter_by(
            prid=project.prid, version=project.version).first()
        if existing:
            if label is not None:
                existing.label = label
        else:
            session.add(ProjectRevisionModel(
                prid=project.prid,
                version=project.version,
                snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                label=label,
            ))
        session.flush()
        rows = session.query(ProjectRevisionModel).filter_by(
            prid=project.prid).order_by(
            ProjectRevisionModel.version.desc()).all()
        for old in rows[REVISION_LIMIT:]:
            session.delete(old)
        session.commit()


def list_revisions(prid: str) -> List[Dict]:
    with SessionLocal() as session:
        rows = session.query(ProjectRevisionModel).filter_by(
            prid=prid).order_by(
            ProjectRevisionModel.version.desc()).all()
        for old in rows[REVISION_LIMIT:]:
            session.delete(old)
        if len(rows) > REVISION_LIMIT:
            session.commit()
        rows = rows[:REVISION_LIMIT]
    result = []
    for row in rows:
        try:
            snapshot = json.loads(row.snapshot_json)
        except Exception:
            continue
        result.append({
            "id": row.id,
            "label": row.label,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "title": snapshot.get("title", ""),
            "event_count": len(snapshot.get("events", [])),
            "wsid": snapshot.get("wsid"),
        })
    return result


def update_revision_label(prid: str, revision_id: int,
                          label: str) -> bool:
    with SessionLocal() as session:
        row = session.query(ProjectRevisionModel).filter_by(
            prid=prid, id=revision_id).first()
        if row is None:
            return False
        row.label = label
        session.commit()
        return True


def delete_revision(prid: str, revision_id: int) -> bool:
    with SessionLocal() as session:
        row = session.query(ProjectRevisionModel).filter_by(
            prid=prid, id=revision_id).first()
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def get_revision(prid: str, revision_id: int) -> Optional[Dict]:
    with SessionLocal() as session:
        row = session.query(ProjectRevisionModel).filter_by(
            prid=prid, id=revision_id).first()
        if row is None:
            return None
        return json.loads(row.snapshot_json)


def project_from_snapshot(snapshot: Dict, prid: str) -> Project:
    tz = _snapshot_timezone(snapshot)
    origin = dt.datetime.fromisoformat(snapshot["origin"])
    plan = plan_from_dict(
        {
            "version": 1,
            "origin": snapshot["origin"],
            "events": snapshot.get("events", []),
        },
        skip_weekends=bool(snapshot.get("skip_weekends")),
        holidays=list(snapshot.get("holidays") or []),
        holiday_ranges=list(snapshot.get("holiday_ranges") or []),
        default_holidays=bool(snapshot.get("default_holidays")),
        timezone=tz,
    )
    workers = [
        Worker(wid=item["wid"], name=item["name"])
        for item in snapshot.get("workers", [])
        if item.get("wid") and item.get("name")
    ]
    ddl_value = snapshot.get("ddl")
    return Project(
        prid=prid,
        title=snapshot.get("title") or "Untitled Project",
        wsid=snapshot.get("wsid"),
        description=snapshot.get("description") or "",
        origin=origin,
        ddl=dt.datetime.fromisoformat(ddl_value) if ddl_value else None,
        events=plan.events,
        workers=workers,
        worker_mode=snapshot.get("worker_mode", "infinite"),
        worker_count=int(snapshot.get("worker_count") or 2),
        single_worker_id=snapshot.get("single_worker_id"),
        active_worker_ids=list(snapshot.get("active_worker_ids") or []),
        capability_mode=snapshot.get("capability_mode", "fallback"),
        deadline_mode=snapshot.get("deadline_mode", "soft"),
        timezone_mode=snapshot.get("timezone_mode", "iana"),
        timezone=snapshot.get("timezone", "Asia/Shanghai"),
        utc_offset_minutes=snapshot.get("utc_offset_minutes"),
        skip_weekends=bool(snapshot.get("skip_weekends")),
        holidays=list(snapshot.get("holidays") or []),
        holiday_ranges=list(snapshot.get("holiday_ranges") or []),
        default_holidays=bool(snapshot.get("default_holidays")),
        version=int(snapshot.get("version") or 1),
    )


def delete_project(prid: str) -> bool:
    with SessionLocal() as session:
        row = session.get(ProjectModel, prid)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
