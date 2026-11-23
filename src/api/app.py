"""FastAPI application for dag-scheduler."""

import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dag_scheduler import (
    CPMScheduler,
    CycleError,
    DEFAULT_ORIGIN,
    DuplicateIDError,
    Plan,
    Project,
    SerializationError,
    Worker,
    Workspace,
    feasibility_report,
    gantt_data,
    plan_from_dict,
    plan_to_dict,
    to_dot,
    to_mermaid,
)
from dag_scheduler.analysis import event_status, what_if
from dag_scheduler.parallel import ParallelScheduler

from . import store

app = FastAPI(title="DAG Scheduler API")
# The Vite dev server serves the frontend separately. Only mount the local
# directory when it exists so an API-only deployment (e.g. Docker) can boot.
if os.path.isdir("frontend"):
    app.mount("/web", StaticFiles(directory="frontend", html=True), name="web")


# ---------- CORS (dev only; tighten for production) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- unified error format ----------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """All HTTP errors become {"error": {"status": ..., "detail": ...}}."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"status": exc.status_code, "detail": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 from Pydantic. Keeps structured errors for field-level feedback."""
    return JSONResponse(
        status_code=422,
        content={"error": {"status": 422, "detail": exc.errors()}},
    )


# ---------- request models ----------
class EventIn(BaseModel):
    eid: str
    description: str
    details: str = ""
    duration: int
    priority: int
    start: str
    deadline: str
    dependencies: List[str] = Field(default_factory=list)
    capable_workers: List[str] = Field(default_factory=list)
    capable_workers_generic: List[int] = Field(default_factory=list)


class PlanIn(BaseModel):
    version: int = 1
    origin: str = "2026-01-01T09:00:00+08:00"
    events: List[EventIn]


class WhatIfIn(BaseModel):
    eid: str
    new_duration: int


class WorkspaceCreateIn(BaseModel):
    name: str
    description: str = ""


class WorkspaceUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WorkerIn(BaseModel):
    wid: Optional[str] = None
    name: str


class HolidayRangeIn(BaseModel):
    start: str
    end: str


class ProjectCreateIn(BaseModel):
    # wsid is optional for backward compatibility: projects created before
    # the workspace UI lands go into the default workspace.
    wsid: Optional[str] = None
    title: str = "Untitled Project"
    description: str = ""
    origin: Optional[str] = None
    ddl: Optional[str] = None
    workers: Optional[List[WorkerIn]] = None
    worker_mode: str = "infinite"
    worker_count: int = 2
    single_worker_id: Optional[str] = None
    active_worker_ids: List[str] = Field(default_factory=list)
    capability_mode: str = "fallback"
    deadline_mode: str = "soft"
    skip_weekends: bool = False
    holidays: List[str] = Field(default_factory=list)
    holiday_ranges: List[HolidayRangeIn] = Field(default_factory=list)
    default_holidays: bool = False
    events: List[EventIn] = Field(default_factory=list)


class ProjectUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    origin: Optional[str] = None
    ddl: Optional[str] = None
    wsid: Optional[str] = None
    workers: Optional[List[WorkerIn]] = None
    worker_mode: Optional[str] = None
    worker_count: Optional[int] = None
    single_worker_id: Optional[str] = None
    active_worker_ids: Optional[List[str]] = None
    capability_mode: Optional[str] = None
    deadline_mode: Optional[str] = None
    skip_weekends: Optional[bool] = None
    holidays: Optional[List[str]] = None
    holiday_ranges: Optional[List[HolidayRangeIn]] = None
    default_holidays: Optional[bool] = None
    events: Optional[List[EventIn]] = None


# ---------- helpers ----------
def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise HTTPException(
            status_code=400, detail=f"{field} must be timezone-aware")
    return parsed


def _normalize_holidays(holidays: Optional[List[str]]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in holidays or []:
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"invalid holiday date: {value!r}") from exc
        iso = parsed.isoformat()
        if iso not in seen:
            seen.add(iso)
            result.append(iso)
    return sorted(result)


def _normalize_holiday_ranges(
        ranges: Optional[List[HolidayRangeIn]]
        ) -> List[dict]:
    result: List[dict] = []
    seen = set()
    for item in ranges or []:
        try:
            start = date.fromisoformat(item.start)
            end = date.fromisoformat(item.end)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"invalid holiday range: {item.start!r} - {item.end!r}"
            ) from exc
        if end < start:
            raise HTTPException(
                status_code=400,
                detail=f"holiday range ends before start: "
                       f"{item.start} - {item.end}")
        key = (start.isoformat(), end.isoformat())
        if key not in seen:
            seen.add(key)
            result.append({"start": key[0], "end": key[1]})
    return result


def _build_plan(events: List[EventIn], origin: datetime,
                skip_weekends: bool = False,
                holidays: Optional[List[str]] = None,
                holiday_ranges: Optional[List[dict]] = None,
                default_holidays: bool = False) -> Plan:
    data = {
        "version": 1,
        "origin": origin.isoformat(),
        "events": [event.model_dump() for event in events],
    }
    try:
        return plan_from_dict(
            data, skip_weekends=skip_weekends, holidays=holidays,
            holiday_ranges=holiday_ranges,
            default_holidays=default_holidays)
    except (SerializationError, ValueError, DuplicateIDError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_origin(origin: Optional[str],
                    events: List[EventIn],
                    fallback: Optional[datetime] = None) -> datetime:
    """Pick an origin that keeps every event on/after it."""
    if origin:
        return _parse_datetime(origin, "origin")

    starts = [
        _parse_datetime(event.start, f"{event.eid}.start")
        for event in events
    ]
    if not starts:
        return fallback or DEFAULT_ORIGIN
    earliest = min(starts)
    if fallback is not None and all(start >= fallback for start in starts):
        return fallback
    return earliest


def _parse_project_ddl(value: Optional[str],
                       origin: datetime) -> Optional[datetime]:
    if value is None:
        return None
    ddl = _parse_datetime(value, "ddl")
    if ddl < origin:
        raise HTTPException(
            status_code=400, detail="ddl must be on or after origin")
    return ddl


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    """Serialize SQLite's naive-UTC timestamps with an explicit UTC offset."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


WORKER_MODES = {"infinite", "1", "workers", "team"}
CAPABILITY_MODES = {"fallback", "strict"}
DEADLINE_MODES = {"soft", "hard"}


def _normalize_worker_settings(mode: str, count: int,
                               single_worker_id: Optional[str],
                               active_worker_ids: Optional[List[str]]
                               ) -> tuple[str, int, Optional[str], List[str]]:
    """Validate the per-project worker mode configuration."""
    if mode not in WORKER_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid worker_mode: {mode!r}")
    if count < 1:
        raise HTTPException(
            status_code=400, detail="worker_count must be >= 1")

    active: List[str] = []
    seen: set[str] = set()
    for wid in active_worker_ids or []:
        if wid in seen:
            raise HTTPException(
                status_code=400,
                detail=f"duplicate active worker id: {wid}")
        seen.add(wid)
        active.append(wid)
    return mode, count, single_worker_id, active


def _validate_enforcement(capability_mode: str, deadline_mode: str,
                          ddl) -> None:
    if capability_mode not in CAPABILITY_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid capability_mode: {capability_mode!r}")
    if deadline_mode not in DEADLINE_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid deadline_mode: {deadline_mode!r}")
    if deadline_mode == "hard" and ddl is None:
        raise HTTPException(
            status_code=400,
            detail="hard deadline requires a project target date")


def _normalize_workers(workers: Optional[List[WorkerIn]]) -> List[Worker]:
    """Normalize a team roster; generate stable ids when omitted."""
    result: List[Worker] = []
    seen: set[str] = set()
    for worker in workers or []:
        name = (worker.name or "").strip()
        if not name:
            raise HTTPException(
                status_code=400, detail="worker name must not be empty")
        wid = (worker.wid or "").strip() or uuid4().hex[:8]
        if wid in seen:
            raise HTTPException(
                status_code=400, detail=f"duplicate worker id: {wid}")
        seen.add(wid)
        result.append(Worker(wid=wid, name=name))
    return result


def _cpm_and_report(plan: Plan, project_ddl=None,
                    deadline_mode: str = "soft"):
    try:
        cpm = CPMScheduler(plan).run()
    except CycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = feasibility_report(
        plan, cpm, project_ddl, deadline_mode=deadline_mode)
    return cpm, {
        "event_count": report.event_count,
        "makespan": report.makespan,
        "makespan_human": report.makespan_human,
        "critical_count": report.critical_count,
        "overdue_count": report.overdue_count,
        "overdue": report.overdue,
        "is_feasible": report.is_feasible,
        "max_concurrency": cpm.max_concurrency,
        "critical_path": cpm.critical_path,
        "project_ddl": report.project_ddl,
        "project_finish": report.project_finish,
        "project_overdue": report.project_overdue,
        "project_late_minutes": report.project_late_minutes,
        "project_late_human": report.project_late_human,
        "deadline_mode": report.deadline_mode,
    }


def _project_or_404(prid: str) -> Project:
    project = store.get_project(prid)
    if project is None:
        raise HTTPException(
            status_code=404, detail=f"project not found: {prid}")
    return project


def _project_plan_or_404(prid: str):
    project = _project_or_404(prid)
    plan = project.to_plan()
    cpm, report = _cpm_and_report(
        plan, project.ddl, project.deadline_mode)
    return project, plan, cpm, report


def _project_payload(project: Project) -> Dict[str, Any]:
    plan = project.to_plan()
    _, report = _cpm_and_report(
        plan, project.ddl, project.deadline_mode)
    project.report = report
    return {
        "prid": project.prid,
        "wsid": project.wsid,
        "title": project.title,
        "description": project.description,
        "origin": plan.origin.isoformat(),
        "ddl": project.ddl.isoformat() if project.ddl else None,
        "events": plan_to_dict(plan)["events"],
        "report": report,
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
        "skip_weekends": project.skip_weekends,
        "holidays": list(project.holidays or []),
        "holiday_ranges": list(project.holiday_ranges or []),
        "default_holidays": project.default_holidays,
        "created_at": _iso_utc(project.created_at),
        "updated_at": _iso_utc(project.updated_at),
    }


def _new_prid() -> str:
    for _ in range(10):
        prid = uuid4().hex[:8]
        if store.get_project(prid) is None:
            return prid
    raise HTTPException(status_code=500, detail="could not allocate a project id")


def _new_wsid() -> str:
    for _ in range(10):
        wsid = uuid4().hex[:8]
        if store.get_workspace(wsid) is None:
            return wsid
    raise HTTPException(status_code=500, detail="could not allocate a workspace id")


def _workspace_or_404(wsid: str) -> Workspace:
    workspace = store.get_workspace(wsid)
    if workspace is None:
        raise HTTPException(
            status_code=404, detail=f"workspace not found: {wsid}")
    return workspace


def _workspace_payload(workspace: Workspace) -> Dict[str, Any]:
    return {
        "wsid": workspace.wsid,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": _iso_utc(workspace.created_at),
        "project_count": len(store.list_projects(wsid=workspace.wsid)),
    }


def _schedule_payload(plan: Plan, workers: int,
                      worker_ids: Optional[List[str]] = None,
                      capability_field: str = "capable_workers",
                      project_ddl=None,
                      deadline_mode: str = "soft"
                      ) -> Dict[str, Any]:
    if workers < 1:
        raise HTTPException(status_code=400, detail="workers must be >= 1")

    result = ParallelScheduler(
        plan, workers, worker_ids=worker_ids,
        capability_field=capability_field).run()
    project_deadline_offset = (
        plan.to_offset(project_ddl) if project_ddl is not None else None)
    tasks_info = {}
    for event in plan.events:
        task_deadline_offset = plan.deadline_offset(event)
        effective_deadline = task_deadline_offset
        if (project_deadline_offset is not None
                and project_deadline_offset < effective_deadline):
            effective_deadline = project_deadline_offset
        status = event_status(event)
        if result.end.get(event.eid, -1) > effective_deadline:
            status = "overdue"
        tasks_info[event.eid] = {
            "description": event.description,
            "priority": event.priority,
            "status": status,
            "capable_workers": list(event.capable_workers or []),
            "capable_workers_generic": list(
                event.capable_workers_generic or []),
        }
    max_end = max(result.end.values(), default=0)
    project_late = (
        max(0, max_end - project_deadline_offset)
        if project_deadline_offset is not None else 0)
    hard_violation = deadline_mode == "hard" and project_late > 0
    task_deadline_violation = any(
        result.end.get(event.eid, -1)
        > plan.deadline_offset(event)
        for event in plan.events
    )
    return {
        "makespan": result.makespan,
        "workers": result.workers,
        "worker_ids": result.worker_ids,
        "capability_fallbacks": result.capability_fallbacks,
        "project_ddl": project_ddl.isoformat() if project_ddl else None,
        "project_finish": plan.to_datetime(max_end).isoformat(),
        "project_overdue": project_late > 0,
        "project_late_minutes": project_late,
        "project_late_human": (
            f"{project_late // 60}h {project_late % 60}m"
            if project_late >= 60 else f"{project_late}m"
        ),
        "deadline_mode": deadline_mode,
        "hard_deadline_violated": hard_violation,
        "is_feasible": not task_deadline_violation and not hard_violation,
        "start": result.start,
        "end": result.end,
        "assignments": result.assignments,
        "tasks": tasks_info,
    }


# ---------- root ----------
@app.get("/")
def root():
    return {
        "name": "DAG Scheduler API",
        "docs": "/docs",
        "endpoints": [
            "GET/POST /workspaces",
            "PUT/DELETE /workspaces/{wsid}",
            "GET/POST /projects",
            "GET/PUT/DELETE /projects/{prid}",
            "GET /projects/{prid}/report",
            "GET /projects/{prid}/gantt",
            "GET /projects/{prid}/schedule?workers=N",
            "GET /projects/{prid}/graph?format=mermaid|dot",
            "POST /plan",
            "GET /plans",
            "GET /plan/{id}",
            "GET /plan/{id}/gantt",
            "GET /plan/{id}/report",
            "GET /plan/{id}/schedule?workers=N",
            "GET /plan/{id}/graph?format=mermaid|dot",
            "POST /plan/{id}/what-if",
            "DELETE /plan/{id}",
        ],
    }


# ---------- workspaces ----------
@app.get("/workspaces")
def list_workspaces():
    return [_workspace_payload(w) for w in store.list_workspaces()]


@app.post("/workspaces", status_code=201)
def create_workspace(data: WorkspaceCreateIn):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="name must not be empty")
    workspace = store.create_workspace(Workspace(
        wsid=_new_wsid(),
        name=data.name.strip(),
        description=data.description or "",
    ))
    return _workspace_payload(workspace)


@app.get("/workspaces/{wsid}")
def get_workspace(wsid: str):
    return _workspace_payload(_workspace_or_404(wsid))


@app.put("/workspaces/{wsid}")
def update_workspace(wsid: str, data: WorkspaceUpdateIn):
    existing = _workspace_or_404(wsid)
    name = data.name if data.name is not None else existing.name
    description = (
        data.description if data.description is not None
        else existing.description)
    if not name.strip():
        raise HTTPException(status_code=400, detail="name must not be empty")
    updated = store.update_workspace(Workspace(
        wsid=wsid,
        name=name.strip(),
        description=description or "",
        created_at=existing.created_at,
    ))
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"workspace not found: {wsid}")
    return _workspace_payload(updated)


@app.delete("/workspaces/{wsid}", status_code=204)
def delete_workspace(wsid: str):
    """Delete a workspace and cascade-delete its projects."""
    if not store.delete_workspace(wsid):
        raise HTTPException(
            status_code=404, detail=f"workspace not found: {wsid}")
    return None


# ---------- transient plan API ----------
@app.post("/plan")
def create_plan(data: PlanIn):
    """Create a plan from JSON and immediately run CPM."""
    try:
        plan = plan_from_dict(data.model_dump())
        cpm = CPMScheduler(plan).run()
    except (SerializationError, ValueError, DuplicateIDError, CycleError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_id = uuid4().hex[:8]
    store.put(plan_id, store.PlanSession(
        plan=plan,
        cpm=cpm,
        created_at=datetime.now(timezone.utc),
    ))
    return {
        "plan_id": plan_id,
        "cpm": {
            "makespan": cpm.makespan,
            "max_concurrency": cpm.max_concurrency,
            "critical_path": cpm.critical_path,
            "overdue": cpm.overdue,
        },
    }


@app.get("/plans")
def list_plans():
    return store.list_sessions()


@app.get("/plan/{plan_id}")
def get_plan(plan_id: str):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    return plan_to_dict(session.plan)


@app.get("/plan/{plan_id}/gantt")
def get_gantt(plan_id: str):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    return gantt_data(session.plan)


@app.get("/plan/{plan_id}/report")
def get_report(plan_id: str):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    _, report = _cpm_and_report(session.plan)
    return report


@app.get("/plan/{plan_id}/schedule")
def get_schedule(plan_id: str, workers: int = 1):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    return _schedule_payload(session.plan, workers)


@app.get("/plan/{plan_id}/graph")
def get_graph(plan_id: str, format: str = "mermaid"):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    if format == "mermaid":
        return {"format": "mermaid",
                "content": to_mermaid(session.plan, session.cpm)}
    if format == "dot":
        return {"format": "dot",
                "content": to_dot(session.plan, session.cpm)}
    raise HTTPException(status_code=400,
                        detail=f"unsupported format: {format}")


@app.post("/plan/{plan_id}/what-if")
def what_if_endpoint(plan_id: str, data: WhatIfIn):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    try:
        return what_if(session.plan, data.eid, data.new_duration)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/plan/{plan_id}", status_code=204)
def delete_plan(plan_id: str):
    if not store.get(plan_id):
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    store.delete(plan_id)
    return None


# ---------- projects ----------
@app.post("/projects", status_code=201)
def create_project(data: ProjectCreateIn):
    """Create a project, optionally inside a workspace.

    Without ``wsid`` the project is placed in the default workspace so the
    existing single-project frontend keeps working.
    """
    events = data.events or []
    origin = _resolve_origin(data.origin, events)
    holidays = _normalize_holidays(data.holidays)
    holiday_ranges = _normalize_holiday_ranges(data.holiday_ranges)
    plan = _build_plan(
        events, origin, data.skip_weekends, holidays,
        holiday_ranges, data.default_holidays)
    _cpm_and_report(plan)  # reject cycles/invalid DAGs before persisting
    ddl = _parse_project_ddl(data.ddl, plan.origin)
    _validate_enforcement(
        data.capability_mode, data.deadline_mode, ddl)
    workspace = (
        _workspace_or_404(data.wsid) if data.wsid
        else store.get_or_create_default_workspace()
    )
    worker_mode, worker_count, single_worker_id, active_worker_ids = (
        _normalize_worker_settings(
            data.worker_mode, data.worker_count,
            data.single_worker_id, data.active_worker_ids))
    project = Project(
        prid=_new_prid(),
        title=data.title or "Untitled Project",
        wsid=workspace.wsid,
        description=data.description or "",
        origin=plan.origin,
        ddl=ddl,
        events=list(plan.events),
        workers=_normalize_workers(data.workers),
        worker_mode=worker_mode,
        worker_count=worker_count,
        single_worker_id=single_worker_id,
        active_worker_ids=active_worker_ids,
        capability_mode=data.capability_mode,
        deadline_mode=data.deadline_mode,
        skip_weekends=data.skip_weekends,
        holidays=holidays,
        holiday_ranges=holiday_ranges,
        default_holidays=data.default_holidays,
    )
    persisted = store.create_project(project)
    return _project_payload(persisted)


@app.get("/projects")
def list_projects(wsid: Optional[str] = None):
    """List projects, optionally filtered by workspace."""
    if wsid is not None:
        _workspace_or_404(wsid)

    summaries = []
    for project in store.list_projects(wsid=wsid):
        plan = project.to_plan()
        _, report = _cpm_and_report(
            plan, project.ddl, project.deadline_mode)
        summaries.append({
            "prid": project.prid,
            "wsid": project.wsid,
            "title": project.title,
            "description": project.description,
            "origin": plan.origin.isoformat(),
            "ddl": project.ddl.isoformat() if project.ddl else None,
            "workers": [
                {"wid": worker.wid, "name": worker.name}
                for worker in (project.workers or [])
            ],
            "capability_mode": project.capability_mode,
            "deadline_mode": project.deadline_mode,
            "skip_weekends": project.skip_weekends,
            "holidays": list(project.holidays or []),
            "holiday_ranges": list(project.holiday_ranges or []),
            "default_holidays": project.default_holidays,
            "event_count": len(plan.events),
            "makespan": report["makespan"],
            "makespan_human": report["makespan_human"],
            "created_at": _iso_utc(project.created_at),
            "updated_at": _iso_utc(project.updated_at),
        })
    return summaries


@app.get("/projects/{prid}")
def get_project(prid: str):
    return _project_payload(_project_or_404(prid))


@app.put("/projects/{prid}")
def update_project(prid: str, data: ProjectUpdateIn):
    """Update project metadata and/or events."""
    existing = _project_or_404(prid)
    fields = data.model_dump(exclude_unset=True)
    events_provided = "events" in fields
    skip_weekends = (
        data.skip_weekends
        if data.skip_weekends is not None else existing.skip_weekends)
    holidays = (
        _normalize_holidays(data.holidays)
        if data.holidays is not None else list(existing.holidays or []))
    holiday_ranges = (
        _normalize_holiday_ranges(data.holiday_ranges)
        if data.holiday_ranges is not None
        else list(existing.holiday_ranges or []))
    default_holidays = (
        data.default_holidays
        if data.default_holidays is not None
        else existing.default_holidays)

    if events_provided:
        events = data.events or []
        origin = _resolve_origin(
            fields.get("origin") if "origin" in fields else None,
            events,
            fallback=existing.origin,
        )
        plan = _build_plan(
            events, origin, skip_weekends, holidays,
            holiday_ranges, default_holidays)
        project_events = list(plan.events)
    else:
        project_events = list(existing.events or [])
        if "origin" in fields and fields["origin"]:
            origin = _parse_datetime(fields["origin"], "origin")
        else:
            origin = existing.resolved_origin()
        try:
            plan = Plan(
                project_events, origin,
                skip_weekends=skip_weekends, holidays=holidays,
                holiday_ranges=holiday_ranges,
                default_holidays=default_holidays)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "ddl" in fields:
        ddl = _parse_project_ddl(fields["ddl"], plan.origin)
    else:
        ddl = existing.ddl
        if ddl is not None and ddl < plan.origin:
            raise HTTPException(
                status_code=400, detail="ddl must be on or after origin")

    capability_mode = (
        data.capability_mode
        if data.capability_mode is not None else existing.capability_mode)
    deadline_mode = (
        data.deadline_mode
        if data.deadline_mode is not None else existing.deadline_mode)
    _validate_enforcement(capability_mode, deadline_mode, ddl)

    _cpm_and_report(plan)  # reject cycles/invalid DAGs before writing

    new_wsid = existing.wsid
    if "wsid" in fields:
        if not fields["wsid"]:
            raise HTTPException(
                status_code=400, detail="wsid must not be empty")
        _workspace_or_404(fields["wsid"])
        new_wsid = fields["wsid"]

    if "workers" in fields:
        workers = _normalize_workers(data.workers or [])
    else:
        workers = list(existing.workers or [])

    worker_mode, worker_count, single_worker_id, active_worker_ids = (
        _normalize_worker_settings(
            data.worker_mode
            if data.worker_mode is not None else existing.worker_mode,
            data.worker_count
            if data.worker_count is not None else existing.worker_count,
            data.single_worker_id
            if "single_worker_id" in fields
            else existing.single_worker_id,
            data.active_worker_ids
            if data.active_worker_ids is not None
            else list(existing.active_worker_ids or []),
        ))

    title = fields.get("title")
    description = fields.get("description")
    project = Project(
        prid=prid,
        title=title if title is not None else existing.title,
        wsid=new_wsid,
        description=(
            description if description is not None else existing.description),
        origin=plan.origin,
        ddl=ddl,
        events=project_events,
        workers=workers,
        worker_mode=worker_mode,
        worker_count=worker_count,
        single_worker_id=single_worker_id,
        active_worker_ids=active_worker_ids,
        capability_mode=capability_mode,
        deadline_mode=deadline_mode,
        skip_weekends=skip_weekends,
        holidays=holidays,
        holiday_ranges=holiday_ranges,
        default_holidays=default_holidays,
    )
    persisted = store.update_project(project)
    if persisted is None:
        raise HTTPException(
            status_code=404, detail=f"project not found: {prid}")
    return _project_payload(persisted)


@app.delete("/projects/{prid}", status_code=204)
def delete_project(prid: str):
    if not store.delete_project(prid):
        raise HTTPException(
            status_code=404, detail=f"project not found: {prid}")
    return None


@app.get("/projects/{prid}/report")
def get_project_report(prid: str):
    _, _, _, report = _project_plan_or_404(prid)
    return report


@app.get("/projects/{prid}/gantt")
def get_project_gantt(prid: str):
    project, plan, _, _ = _project_plan_or_404(prid)
    return gantt_data(plan, project.ddl)


@app.get("/projects/{prid}/schedule")
def get_project_schedule(prid: str, workers: int = 1,
                         worker_ids: Optional[str] = None):
    project, plan, _, _ = _project_plan_or_404(prid)
    roster = list(project.workers or [])
    roster_ids = {worker.wid for worker in roster}

    if not worker_ids and workers < 1:
        raise HTTPException(
            status_code=400, detail="workers must be >= 1")

    active_ids: Optional[List[str]] = None
    if worker_ids:
        if not roster:
            raise HTTPException(
                status_code=400,
                detail="project has no named workers")
        requested = [
            item.strip() for item in worker_ids.split(",") if item.strip()]
        if not requested:
            raise HTTPException(
                status_code=400, detail="worker_ids must not be empty")
        if len(set(requested)) != len(requested):
            raise HTTPException(
                status_code=400, detail="duplicate worker ids")
        unknown = [wid for wid in requested if wid not in roster_ids]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"unknown worker ids: {', '.join(unknown)}")
        active_ids = requested
        workers = len(requested)

    capability_field = (
        "capable_workers" if worker_ids else "capable_workers_generic")

    if project.capability_mode == "strict":
        active_set = (
            set(active_ids) if active_ids is not None
            else set(range(workers)))
        missing = []
        for event in plan.events:
            capable = set(getattr(event, capability_field, []) or [])
            if capable and not (capable & active_set):
                missing.append(event.eid)
        if missing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "strict capability mode: no active capable worker for "
                    + ", ".join(sorted(missing))))

    return _schedule_payload(
        plan, workers, active_ids, capability_field=capability_field,
        project_ddl=project.ddl, deadline_mode=project.deadline_mode)


@app.get("/projects/{prid}/graph")
def get_project_graph(prid: str, format: str = "mermaid"):
    _, plan, cpm, _ = _project_plan_or_404(prid)
    if format == "mermaid":
        return {"format": "mermaid", "content": to_mermaid(plan, cpm)}
    if format == "dot":
        return {"format": "dot", "content": to_dot(plan, cpm)}
    raise HTTPException(status_code=400,
                        detail=f"unsupported format: {format}")
