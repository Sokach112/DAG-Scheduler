"""FastAPI application for dag-scheduler."""

import os
from datetime import datetime, timezone
from typing import Optional
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
    feasibility_report,
    gantt_data,
    plan_from_dict,
    plan_to_dict,
    to_dot,
    to_mermaid,
)
from dag_scheduler.analysis import _status
from dag_scheduler.parallel import ParallelScheduler

from . import store

app = FastAPI(title="DAG Scheduler API")
# The Vite dev server serves the frontend separately. Only mount the local
# directory when it exists so an API-only deployment (e.g. Docker) can boot.
if os.path.isdir("frontend"):
    app.mount("/web", StaticFiles(directory="frontend", html=True), name="web")


class WhatIfIn(BaseModel):
    eid: str
    new_duration: int


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
    dependencies: list[str] = Field(default_factory=list)


class PlanIn(BaseModel):
    version: int = 1
    origin: str = "2026-01-01T09:00:00+08:00"
    events: list[EventIn]


class ProjectIn(BaseModel):
    title: str = "Untitled Project"
    description: str = ""
    origin: Optional[str] = None
    ddl: Optional[str] = None
    events: list[EventIn] = Field(default_factory=list)


class ProjectUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    origin: Optional[str] = None
    ddl: Optional[str] = None
    events: Optional[list[EventIn]] = None


# ---------- helpers ----------
def _session_or_404(plan_id: str) -> store.PlanSession:
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    return session


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail=f"{field} must be timezone-aware")
    return parsed


def _build_plan(events: list[EventIn], origin: datetime) -> Plan:
    data = {
        "version": 1,
        "origin": origin.isoformat(),
        "events": [event.model_dump() for event in events],
    }
    try:
        return plan_from_dict(data)
    except (SerializationError, ValueError, DuplicateIDError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_origin(origin: Optional[str],
                    events: list[EventIn],
                    fallback: Optional[datetime] = None) -> datetime:
    """Pick an origin that keeps every event on/after it.

    An explicit origin wins and is validated by Plan. Otherwise an existing
    (fallback) origin is kept when still valid, and the earliest event start
    is used when tasks moved before it.
    """
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


def _cpm_and_report(plan: Plan):
    try:
        cpm = CPMScheduler(plan).run()
    except CycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = feasibility_report(plan, cpm)
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
    cpm, report = _cpm_and_report(plan)
    return project, plan, cpm, report


def _project_payload(project: Project) -> dict:
    plan = project.to_plan()
    _, report = _cpm_and_report(plan)
    project.report = report
    return {
        "prid": project.prid,
        "title": project.title,
        "description": project.description,
        "origin": plan.origin.isoformat(),
        "ddl": project.ddl.isoformat() if project.ddl else None,
        "events": plan_to_dict(plan)["events"],
        "report": report,
    }


def _new_prid() -> str:
    for _ in range(10):
        prid = uuid4().hex[:8]
        if store.get_project(prid) is None:
            return prid
    raise HTTPException(
        status_code=500, detail="could not allocate a project id")


def _schedule_payload(plan: Plan, workers: int) -> dict:
    if workers < 1:
        raise HTTPException(status_code=400, detail="workers must be >= 1")

    result = ParallelScheduler(plan, workers).run()
    tasks_info = {}
    for event in plan.events:
        tasks_info[event.eid] = {
            "description": event.description,
            "priority": event.priority,
            "status": _status(event),
        }
    return {
        "makespan": result.makespan,
        "workers": result.workers,
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
            "POST /plan",
            "GET /plans",
            "GET /plan/{id}",
            "GET /plan/{id}/gantt",
            "GET /plan/{id}/report",
            "GET /plan/{id}/schedule?workers=N",
            "GET /plan/{id}/graph?format=mermaid|dot",
            "DELETE /plan/{id}",
            "POST /projects",
            "GET /projects",
            "GET /projects/{prid}",
            "PUT /projects/{prid}",
            "DELETE /projects/{prid}",
            "GET /projects/{prid}/report",
            "GET /projects/{prid}/gantt",
            "GET /projects/{prid}/schedule?workers=N",
            "GET /projects/{prid}/graph?format=mermaid|dot",
        ],
    }


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
    """List all stored plans (summary)."""
    return store.list_sessions()


@app.get("/plan/{plan_id}")
def get_plan(plan_id: str):
    """Return the original plan as JSON (serializer format)."""
    session = _session_or_404(plan_id)
    return plan_to_dict(session.plan)


@app.get("/plan/{plan_id}/gantt")
def get_gantt(plan_id: str):
    """Gantt data: one row per event with absolute ISO times."""
    session = _session_or_404(plan_id)
    return gantt_data(session.plan)


@app.get("/plan/{plan_id}/report")
def get_report(plan_id: str):
    session = _session_or_404(plan_id)
    _, report = _cpm_and_report(session.plan)
    return report


@app.get("/plan/{plan_id}/schedule")
def get_schedule(plan_id: str, workers: int = 1):
    """Resource-constrained schedule with the given number of workers."""
    session = _session_or_404(plan_id)
    return _schedule_payload(session.plan, workers)


@app.get("/plan/{plan_id}/graph")
def get_graph(plan_id: str, format: str = "mermaid"):
    """Graph export. format=mermaid or format=dot."""
    session = _session_or_404(plan_id)
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
    """Compare makespan after changing one event's duration."""
    session = _session_or_404(plan_id)
    from dag_scheduler.analysis import what_if
    try:
        return what_if(session.plan, data.eid, data.new_duration)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/plan/{plan_id}", status_code=204)
def delete_plan(plan_id: str):
    """Delete a stored plan. 204 on success, 404 if not found."""
    if not store.get(plan_id):
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    store.delete(plan_id)
    return None


# ---------- persistent projects ----------
@app.post("/projects", status_code=201)
def create_project(data: ProjectIn):
    """Create and persist a project, then return it with its CPM report."""
    events = data.events or []
    origin = _resolve_origin(data.origin, events)
    plan = _build_plan(events, origin)
    _cpm_and_report(plan)  # reject cycles/invalid DAGs before persisting
    ddl = _parse_project_ddl(data.ddl, plan.origin)
    project = Project(
        prid=_new_prid(),
        title=data.title or "Untitled Project",
        description=data.description or "",
        origin=plan.origin,
        ddl=ddl,
        events=list(plan.events),
    )
    store.create_project(project)
    return _project_payload(project)


@app.get("/projects")
def list_projects():
    """List persisted projects, newest first."""
    summaries = []
    for project in store.list_projects():
        plan = project.to_plan()
        _, report = _cpm_and_report(plan)
        summaries.append({
            "prid": project.prid,
            "title": project.title,
            "description": project.description,
            "origin": plan.origin.isoformat(),
            "ddl": project.ddl.isoformat() if project.ddl else None,
            "event_count": len(plan.events),
            "makespan": report["makespan"],
            "makespan_human": report["makespan_human"],
        })
    return summaries


@app.get("/projects/{prid}")
def get_project(prid: str):
    """Return a project with its events and computed report."""
    return _project_payload(_project_or_404(prid))


@app.put("/projects/{prid}")
def update_project(prid: str, data: ProjectUpdateIn):
    """Update project metadata and/or events.

    Only fields present in the request body are changed. When events move
    before the current origin and no new origin is supplied, the origin is
    rebased to the earliest event automatically.
    """
    existing = _project_or_404(prid)
    fields = data.model_dump(exclude_unset=True)
    events_provided = "events" in fields

    if events_provided:
        events = data.events or []
        origin = _resolve_origin(
            fields.get("origin") if "origin" in fields else None,
            events,
            fallback=existing.origin,
        )
        plan = _build_plan(events, origin)
        project_events = list(plan.events)
    else:
        project_events = list(existing.events or [])
        if "origin" in fields and fields["origin"]:
            origin = _parse_datetime(fields["origin"], "origin")
        else:
            origin = existing.resolved_origin()
        try:
            plan = Plan(project_events, origin)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "ddl" in fields:
        ddl = _parse_project_ddl(fields["ddl"], plan.origin)
    else:
        ddl = existing.ddl
        if ddl is not None and ddl < plan.origin:
            raise HTTPException(
                status_code=400, detail="ddl must be on or after origin")

    _cpm_and_report(plan)  # reject cycles/invalid DAGs before writing

    title = fields.get("title")
    description = fields.get("description")
    project = Project(
        prid=prid,
        title=title if title is not None else existing.title,
        description=(
            description if description is not None else existing.description),
        origin=plan.origin,
        ddl=ddl,
        events=project_events,
    )
    if store.update_project(project) is None:
        raise HTTPException(
            status_code=404, detail=f"project not found: {prid}")
    return _project_payload(project)


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
    _, plan, _, _ = _project_plan_or_404(prid)
    return gantt_data(plan)


@app.get("/projects/{prid}/schedule")
def get_project_schedule(prid: str, workers: int = 1):
    _, plan, _, _ = _project_plan_or_404(prid)
    return _schedule_payload(plan, workers)


@app.get("/projects/{prid}/graph")
def get_project_graph(prid: str, format: str = "mermaid"):
    _, plan, cpm, _ = _project_plan_or_404(prid)
    if format == "mermaid":
        return {"format": "mermaid", "content": to_mermaid(plan, cpm)}
    if format == "dot":
        return {"format": "dot", "content": to_dot(plan, cpm)}
    raise HTTPException(status_code=400,
                        detail=f"unsupported format: {format}")
