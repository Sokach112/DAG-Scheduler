"""FastAPI application for dag-scheduler."""

import io
import json
import os
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

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
from dag_scheduler.default_holidays import holiday_coverage
from dag_scheduler.parallel import ParallelScheduler

from . import auth, store

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

AUTH_PREFIXES = ("/workspaces", "/projects", "/plans", "/plan",
                 "/holidays", "/admin", "/users")


@app.middleware("http")
async def session_auth_middleware(request: Request, call_next):
    path = request.url.path
    protected = any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in AUTH_PREFIXES)
    if not protected or request.method == "OPTIONS":
        return await call_next(request)
    user = auth.current_user(request)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"error": {
                "status": 401,
                "detail": "authentication required",
            }},
        )
    request.state.user = user
    return await call_next(request)


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


class AuthBootstrapIn(BaseModel):
    username: str
    display_name: str = ""
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class AdminUserCreateIn(BaseModel):
    username: str
    display_name: str = ""
    password: str
    is_admin: bool = False
    workspace_ids: List[str] = Field(default_factory=list)
    workspace_role: str = "editor"


class MemberCreateIn(BaseModel):
    user_id: str
    role: str = "editor"


class MemberUpdateIn(BaseModel):
    role: str


class WorkerIn(BaseModel):
    wid: Optional[str] = None
    name: str


class HolidayRangeIn(BaseModel):
    start: str
    end: str


class ProjectCreateIn(BaseModel):
    # wsid is optional for backward compatibility: projects created before
    # the workspace UI lands go into the default workspace.
    prid: Optional[str] = None
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
    timezone_mode: str = "iana"
    timezone: str = "Asia/Shanghai"
    utc_offset_minutes: Optional[int] = None
    skip_weekends: bool = False
    holidays: List[str] = Field(default_factory=list)
    holiday_ranges: List[HolidayRangeIn] = Field(default_factory=list)
    default_holidays: bool = False
    events: List[EventIn] = Field(default_factory=list)


class ProjectVersionCreateIn(BaseModel):
    label: Optional[str] = None


class ProjectVersionUpdateIn(BaseModel):
    label: str


class ProjectRestoreIn(BaseModel):
    version: int
    revision_id: int


class ProjectUpdateIn(BaseModel):
    version: int
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
    timezone_mode: Optional[str] = None
    timezone: Optional[str] = None
    utc_offset_minutes: Optional[int] = None
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


def _normalize_timezone(mode: str, name: str,
                        offset_minutes: Optional[int]) -> tuple:
    if mode not in TIMEZONE_MODES:
        raise HTTPException(
            status_code=400, detail=f"invalid timezone_mode: {mode!r}")
    if mode == "iana":
        try:
            ZoneInfo(name)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"invalid IANA timezone: {name!r}") from exc
        return mode, name, None

    if offset_minutes is None:
        raise HTTPException(
            status_code=400,
            detail="fixed timezone requires utc_offset_minutes")
    if offset_minutes < -600 or offset_minutes > 840:
        raise HTTPException(
            status_code=400,
            detail="utc_offset_minutes must be between -600 and 840")
    if offset_minutes % 15 != 0:
        raise HTTPException(
            status_code=400,
            detail="utc_offset_minutes must use 15-minute steps")
    return mode, name, offset_minutes


def _tzinfo(mode: str, name: str,
            offset_minutes: Optional[int]):
    if mode == "fixed":
        return timezone(timedelta(minutes=offset_minutes or 0))
    return ZoneInfo(name)


def _reinterpret_wall(dt: datetime, tzinfo) -> datetime:
    """Preserve wall-clock fields while changing the project timezone."""
    return dt.replace(tzinfo=tzinfo)


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
                default_holidays: bool = False,
                tzinfo=None) -> Plan:
    data = {
        "version": 1,
        "origin": origin.isoformat(),
        "events": [event.model_dump() for event in events],
    }
    try:
        return plan_from_dict(
            data, skip_weekends=skip_weekends, holidays=holidays,
            holiday_ranges=holiday_ranges,
            default_holidays=default_holidays,
            timezone=tzinfo)
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
TIMEZONE_MODES = {"iana", "fixed"}


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
        "timezone_mode": project.timezone_mode,
        "timezone": project.timezone,
        "utc_offset_minutes": project.utc_offset_minutes,
        "skip_weekends": project.skip_weekends,
        "holidays": list(project.holidays or []),
        "holiday_ranges": list(project.holiday_ranges or []),
        "default_holidays": project.default_holidays,
        "holiday_coverage": holiday_coverage(),
        "version": project.version,
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


ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}
VALID_ROLES = set(ROLE_RANK)


def _role_for_workspace(user: Dict, wsid: str) -> Optional[str]:
    if user.get("is_admin"):
        return "owner"
    return store.get_workspace_role(wsid, user["id"])


def _require_workspace(request: Request, wsid: str,
                       minimum: str = "viewer") -> Dict:
    user = auth.require_user(request)
    _workspace_or_404(wsid)
    role = _role_for_workspace(user, wsid)
    if role is None or ROLE_RANK.get(role, 0) < ROLE_RANK[minimum]:
        raise HTTPException(
            status_code=403,
            detail="you do not have access to this workspace")
    return user


def _require_project(request: Request, prid: str,
                     minimum: str = "viewer") -> Project:
    user = auth.require_user(request)
    project = _project_or_404(prid)
    role = _role_for_workspace(user, project.wsid)
    if role is None or ROLE_RANK.get(role, 0) < ROLE_RANK[minimum]:
        raise HTTPException(
            status_code=403,
            detail="you do not have access to this project")
    return project


def _workspace_payload(workspace: Workspace,
                       role: Optional[str] = None) -> Dict[str, Any]:
    return {
        "wsid": workspace.wsid,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": _iso_utc(workspace.created_at),
        "project_count": len(store.list_projects(wsid=workspace.wsid)),
        "role": role,
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


MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_IMPORT_PROJECTS = 200


def _safe_filename(value: str, fallback: str = "workspace") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-")
    return value[:60] or fallback


def _project_import_model(raw: Any, wsid: str) -> "ProjectCreateIn":
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="project JSON must be an object")
    data = raw.get("project", raw)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid project wrapper")
    data = dict(data)
    data.pop("version", None)
    data["wsid"] = wsid
    try:
        return ProjectCreateIn(**data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"invalid project: {exc.errors()[0].get('msg', 'validation error')}",
        ) from exc


DUPLICATE_STRATEGIES = {"cancel", "new", "replace"}


def _duplicate_response(kind: str, workspace_ids: List[str],
                        project_ids: List[str]) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "status": 409,
                "detail": "duplicate IDs",
                "kind": kind,
                "duplicates": {
                    "workspace": workspace_ids,
                    "projects": project_ids,
                },
            }
        },
    )


def _workspace_zip(wsid: str) -> tuple[bytes, str]:
    workspace = store.get_workspace(wsid)
    if workspace is None:
        raise HTTPException(
            status_code=404, detail=f"workspace not found: {wsid}")
    projects = store.list_projects(wsid)
    files: List[str] = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, project in enumerate(projects, start=1):
            name = (
                f"projects/{index:03d}-"
                f"{_safe_filename(project.title, 'project')}.json")
            archive.writestr(
                name,
                json.dumps(store.project_export_payload(project),
                           ensure_ascii=False, indent=2))
            files.append(name)
        manifest = {
            "format": "dag-scheduler-workspace",
            "schema_version": 1,
            "workspace": {
                "wsid": workspace.wsid,
                "name": workspace.name,
                "description": workspace.description,
            },
            "projects": files,
        }
        archive.writestr(
            "workspace.json",
            json.dumps(manifest, ensure_ascii=False, indent=2))
    return buffer.getvalue(), (
        f"{_safe_filename(workspace.name, 'workspace')}.zip")


def _workspace_import(blob: bytes, strategy: str = "cancel",
                      user: Optional[Dict] = None) -> Dict:
    if strategy not in DUPLICATE_STRATEGIES:
        raise HTTPException(status_code=400, detail="invalid on_duplicate")
    if len(blob) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="workspace ZIP is too large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="invalid workspace ZIP") from exc

    with archive:
        names = archive.namelist()
        if sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="workspace contents are too large")
        manifest: Dict = {}
        if "workspace.json" in names:
            try:
                manifest = json.loads(archive.read("workspace.json"))
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail="invalid workspace.json") from exc
        if not isinstance(manifest, dict):
            raise HTTPException(
                status_code=400, detail="workspace.json must be an object")

        project_files = [
            name for name in (manifest.get("projects") or [])
            if isinstance(name, str) and name in names
        ]
        if not project_files:
            project_files = [
                name for name in names
                if name.endswith(".json") and name != "workspace.json"
            ]
        project_files = sorted(dict.fromkeys(project_files))
        if len(project_files) > MAX_IMPORT_PROJECTS:
            raise HTTPException(
                status_code=400, detail="too many projects in workspace ZIP")

        models = []
        for name in project_files:
            try:
                raw = json.loads(archive.read(name))
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid project JSON: {name}") from exc
            models.append(_project_import_model(raw, ""))

    workspace_meta = manifest.get("workspace") or {}
    if not isinstance(workspace_meta, dict):
        workspace_meta = {}
    original_wsid = str(workspace_meta.get("wsid") or "").strip()
    workspace_exists = bool(
        original_wsid and store.get_workspace(original_wsid))
    duplicate_projects = [
        model.prid for model in models
        if model.prid and store.get_project(model.prid)
    ]
    if workspace_exists and strategy == "replace":
        if user is None:
            raise HTTPException(status_code=401, detail="authentication required")
        role = _role_for_workspace(user, original_wsid)
        if role != "owner":
            raise HTTPException(
                status_code=403,
                detail="workspace owner access required for replacement")
    if strategy == "replace" and duplicate_projects:
        if user is None:
            raise HTTPException(
                status_code=401, detail="authentication required")
        for pid in duplicate_projects:
            existing_project = store.get_project(pid)
            if existing_project is None:
                continue
            role = _role_for_workspace(user, existing_project.wsid)
            if role not in {"owner", "editor"}:
                raise HTTPException(
                    status_code=403,
                    detail="editor access required for replaced projects")
    if (workspace_exists or duplicate_projects) and strategy == "cancel":
        return _duplicate_response(
            "workspace",
            [original_wsid] if workspace_exists else [],
            list(dict.fromkeys(duplicate_projects)),
        )

    target_wsid = original_wsid or _new_wsid()
    if workspace_exists and strategy == "new":
        target_wsid = _new_wsid()

    for model in models:
        model.wsid = target_wsid
        if (strategy == "new" and model.prid
                and store.get_project(model.prid)):
            model.prid = None

    # Validate every project before replacing/deleting anything.
    built = [
        _build_project_from_in(model, wsid=target_wsid)
        for model in models
    ]

    if workspace_exists and strategy == "replace":
        store.delete_workspace(original_wsid)

    name = (workspace_meta.get("name") or manifest.get("name")
            or "Imported workspace")
    description = (workspace_meta.get("description")
                   or manifest.get("description") or "")
    workspace = store.create_workspace(Workspace(
        wsid=target_wsid,
        name=str(name)[:120] or "Imported workspace",
        description=str(description)[:2000],
    ))
    if user is not None:
        store.add_workspace_member(workspace.wsid, user["id"], "owner")

    created = []
    try:
        for project in built:
            existing = store.get_project(project.prid)
            if existing is not None and strategy == "replace":
                updated = store.update_project(project, existing.version)
                if updated is None:
                    raise HTTPException(
                        status_code=409,
                        detail="version conflict while replacing project")
                created.append(_project_payload(updated))
            elif existing is not None:
                project.prid = _new_prid()
                created.append(_project_payload(
                    store.create_project(project)))
            else:
                created.append(_project_payload(
                    store.create_project(project)))
    except Exception:
        store.delete_workspace(workspace.wsid)
        raise
    return {
        "workspace": _workspace_payload(workspace),
        "projects": created,
    }


# ---------- auth ----------
@app.get("/auth/status")
def auth_status(request: Request):
    user = auth.current_user(request)
    return {
        "needs_setup": not store.has_users(),
        "authenticated": user is not None,
        "user": auth.user_payload(user) if user else None,
    }


@app.post("/auth/bootstrap", status_code=201)
def auth_bootstrap(data: AuthBootstrapIn, request: Request,
                   response: Response):
    if store.has_users():
        raise HTTPException(
            status_code=409, detail="setup has already been completed")
    username = auth.normalize_username(data.username)
    password = auth.validate_password(data.password)
    if store.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    user = store.create_user(
        username=username,
        display_name=(data.display_name or username).strip(),
        password_hash=auth.hash_password(password),
        is_admin=True,
    )
    store.assign_all_workspaces(user["id"], "owner")
    auth.start_session(response, user["id"])
    return auth.user_payload(user)


@app.post("/auth/login")
def auth_login(data: LoginIn, request: Request, response: Response):
    username = (data.username or "").strip().lower()
    user = store.get_user_by_username(username)
    if (user is None or not user.get("is_active")
            or not auth.verify_password(data.password, user["password_hash"])):
        raise HTTPException(
            status_code=401, detail="invalid username or password")
    auth.start_session(response, user["id"])
    return auth.user_payload(user)


@app.post("/auth/logout")
def auth_logout(request: Request, response: Response):
    auth.end_session(request, response)
    return {"ok": True}


@app.get("/auth/me")
def auth_me(request: Request):
    return auth.user_payload(auth.require_user(request))


@app.post("/auth/change-password")
def auth_change_password(data: ChangePasswordIn, request: Request):
    user = auth.require_user(request)
    record = store.get_user_by_username(user["username"])
    if record is None or not auth.verify_password(
            data.current_password, record["password_hash"]):
        raise HTTPException(
            status_code=400, detail="current password is incorrect")
    password = auth.validate_password(data.new_password)
    store.set_user_password(user["id"], auth.hash_password(password))
    return {"ok": True}


@app.get("/users")
def list_user_directory(request: Request):
    auth.require_user(request)
    return [
        {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "is_admin": user["is_admin"],
        }
        for user in store.list_users()
        if user.get("is_active", True)
    ]


@app.get("/admin/users")
def admin_list_users(request: Request):
    auth.require_admin(request)
    return store.list_users()


@app.post("/admin/users", status_code=201)
def admin_create_user(data: AdminUserCreateIn, request: Request):
    auth.require_admin(request)
    username = auth.normalize_username(data.username)
    password = auth.validate_password(data.password)
    if store.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    if data.workspace_role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="invalid workspace role")
    for wsid in data.workspace_ids:
        _workspace_or_404(wsid)
    user = store.create_user(
        username=username,
        display_name=(data.display_name or username).strip(),
        password_hash=auth.hash_password(password),
        is_admin=data.is_admin,
    )
    for wsid in data.workspace_ids:
        store.add_workspace_member(wsid, user["id"], data.workspace_role)
    return user


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
def list_workspaces(request: Request):
    user = auth.require_user(request)
    workspaces = store.list_workspaces()
    if not user.get("is_admin"):
        allowed = set(store.workspace_ids_for_user(user["id"]))
        workspaces = [w for w in workspaces if w.wsid in allowed]
    return [
        _workspace_payload(w, _role_for_workspace(user, w.wsid))
        for w in workspaces
    ]


@app.post("/workspaces", status_code=201)
def create_workspace(data: WorkspaceCreateIn, request: Request):
    user = auth.require_user(request)
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="name must not be empty")
    workspace = store.create_workspace(Workspace(
        wsid=_new_wsid(),
        name=data.name.strip(),
        description=data.description or "",
    ))
    store.add_workspace_member(workspace.wsid, user["id"], "owner")
    return _workspace_payload(workspace, "owner")


@app.get("/workspaces/{wsid}")
def get_workspace(wsid: str, request: Request):
    user = _require_workspace(request, wsid, "viewer")
    return _workspace_payload(
        _workspace_or_404(wsid), _role_for_workspace(user, wsid))


@app.put("/workspaces/{wsid}")
def update_workspace(wsid: str, data: WorkspaceUpdateIn,
                     request: Request):
    _require_workspace(request, wsid, "owner")
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
    user = auth.require_user(request)
    return _workspace_payload(updated, _role_for_workspace(user, wsid))


@app.delete("/workspaces/{wsid}", status_code=204)
def delete_workspace(wsid: str, request: Request):
    """Delete a workspace and cascade-delete its projects."""
    _require_workspace(request, wsid, "owner")
    if not store.delete_workspace(wsid):
        raise HTTPException(
            status_code=404, detail=f"workspace not found: {wsid}")
    return None


@app.get("/workspaces/{wsid}/members")
def list_workspace_members(wsid: str, request: Request):
    _require_workspace(request, wsid, "owner")
    return store.list_workspace_members(wsid)


@app.post("/workspaces/{wsid}/members", status_code=201)
def add_workspace_member(wsid: str, data: MemberCreateIn,
                         request: Request):
    _require_workspace(request, wsid, "owner")
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="invalid role")
    if store.get_user(data.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    store.add_workspace_member(wsid, data.user_id, data.role)
    return next(
        member for member in store.list_workspace_members(wsid)
        if member["id"] == data.user_id)


@app.patch("/workspaces/{wsid}/members/{user_id}")
def update_workspace_member(wsid: str, user_id: str, data: MemberUpdateIn,
                            request: Request):
    _require_workspace(request, wsid, "owner")
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="invalid role")
    members = store.list_workspace_members(wsid)
    current = next((m for m in members if m["id"] == user_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="member not found")
    if (current["role"] == "owner" and data.role != "owner"
            and sum(1 for m in members if m["role"] == "owner") <= 1):
        raise HTTPException(
            status_code=400, detail="workspace must keep at least one owner")
    store.update_workspace_member(wsid, user_id, data.role)
    return {"ok": True}


@app.delete("/workspaces/{wsid}/members/{user_id}", status_code=204)
def remove_workspace_member(wsid: str, user_id: str, request: Request):
    _require_workspace(request, wsid, "owner")
    members = store.list_workspace_members(wsid)
    current = next((m for m in members if m["id"] == user_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="member not found")
    if (current["role"] == "owner"
            and sum(1 for m in members if m["role"] == "owner") <= 1):
        raise HTTPException(
            status_code=400, detail="workspace must keep at least one owner")
    store.remove_workspace_member(wsid, user_id)
    return None


@app.get("/workspaces/{wsid}/export")
def export_workspace(wsid: str, request: Request):
    _require_workspace(request, wsid, "viewer")
    content, filename = _workspace_zip(wsid)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@app.post("/workspaces/import", status_code=201)
async def import_workspace(request: Request, on_duplicate: str = "cancel"):
    user = auth.require_user(request)
    blob = await request.body()
    return _workspace_import(blob, on_duplicate.strip().lower(), user)


# ---------- transient plan API ----------
def _plan_or_404(plan_id: str, request: Request):
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    user = auth.require_user(request)
    if not user.get("is_admin") and session.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="plan access denied")
    return session


@app.post("/plan")
def create_plan(data: PlanIn, request: Request):
    """Create a plan from JSON and immediately run CPM."""
    try:
        plan = plan_from_dict(data.model_dump())
        cpm = CPMScheduler(plan).run()
    except (SerializationError, ValueError, DuplicateIDError, CycleError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = auth.require_user(request)
    plan_id = uuid4().hex[:8]
    store.put(plan_id, store.PlanSession(
        plan=plan,
        cpm=cpm,
        created_at=datetime.now(timezone.utc),
        user_id=user["id"],
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
def list_plans(request: Request):
    user = auth.require_user(request)
    sessions = store.list_sessions()
    if not user.get("is_admin"):
        sessions = [
            item for item in sessions if item.get("user_id") == user["id"]]
    return sessions


@app.get("/plan/{plan_id}")
def get_plan(plan_id: str, request: Request):
    session = _plan_or_404(plan_id, request)
    return plan_to_dict(session.plan)


@app.get("/plan/{plan_id}/gantt")
def get_gantt(plan_id: str, request: Request):
    session = _plan_or_404(plan_id, request)
    return gantt_data(session.plan)


@app.get("/plan/{plan_id}/report")
def get_report(plan_id: str, request: Request):
    session = _plan_or_404(plan_id, request)
    _, report = _cpm_and_report(session.plan)
    return report


@app.get("/plan/{plan_id}/schedule")
def get_schedule(plan_id: str, request: Request, workers: int = 1):
    session = _plan_or_404(plan_id, request)
    return _schedule_payload(session.plan, workers)


@app.get("/plan/{plan_id}/graph")
def get_graph(plan_id: str, request: Request, format: str = "mermaid"):
    session = _plan_or_404(plan_id, request)
    if format == "mermaid":
        return {"format": "mermaid",
                "content": to_mermaid(session.plan, session.cpm)}
    if format == "dot":
        return {"format": "dot",
                "content": to_dot(session.plan, session.cpm)}
    raise HTTPException(status_code=400,
                        detail=f"unsupported format: {format}")


@app.post("/plan/{plan_id}/what-if")
def what_if_endpoint(plan_id: str, data: WhatIfIn, request: Request):
    session = _plan_or_404(plan_id, request)
    try:
        return what_if(session.plan, data.eid, data.new_duration)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/plan/{plan_id}", status_code=204)
def delete_plan(plan_id: str, request: Request):
    _plan_or_404(plan_id, request)
    store.delete(plan_id)
    return None


# ---------- holiday metadata ----------
@app.get("/holidays/coverage")
def get_holiday_coverage():
    return holiday_coverage()


# ---------- projects ----------
@app.get("/projects/{prid}/export")
def export_project(prid: str, request: Request):
    project = _require_project(request, prid, "viewer")
    filename = f"{_safe_filename(project.title, 'project')}.json"
    return JSONResponse(
        content=store.project_export_payload(project),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@app.post("/projects/import", status_code=201)
async def import_project(request: Request, wsid: Optional[str] = None,
                         on_duplicate: str = "cancel"):
    auth.require_user(request)
    strategy = on_duplicate.strip().lower()
    if strategy not in DUPLICATE_STRATEGIES:
        raise HTTPException(status_code=400, detail="invalid on_duplicate")
    blob = await request.body()
    if len(blob) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="project JSON is too large")
    try:
        raw = json.loads(blob)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid project JSON") from exc
    target = wsid or store.get_or_create_default_workspace().wsid
    if store.get_workspace(target) is None:
        raise HTTPException(
            status_code=404, detail=f"workspace not found: {target}")
    _require_workspace(request, target, "editor")

    model = _project_import_model(raw, target)
    existing = store.get_project(model.prid) if model.prid else None
    if existing is not None:
        _require_workspace(request, existing.wsid, "editor")
    if existing is not None and strategy == "cancel":
        return _duplicate_response("project", [], [model.prid])
    if existing is not None and strategy == "new":
        model.prid = None

    project = _build_project_from_in(model, wsid=target)
    if existing is not None and strategy == "replace":
        updated = store.update_project(project, existing.version)
        if updated is None:
            raise HTTPException(
                status_code=409,
                detail="version conflict while replacing project")
        return _project_payload(updated)
    persisted = store.create_project(project)
    return _project_payload(persisted)


def _build_project_from_in(data: ProjectCreateIn,
                           wsid: Optional[str] = None) -> Project:
    events = data.events or []
    origin = _resolve_origin(data.origin, events)
    timezone_mode, timezone_name, utc_offset_minutes = _normalize_timezone(
        data.timezone_mode, data.timezone, data.utc_offset_minutes)
    project_tz = _tzinfo(
        timezone_mode, timezone_name, utc_offset_minutes)
    holidays = _normalize_holidays(data.holidays)
    holiday_ranges = _normalize_holiday_ranges(data.holiday_ranges)
    plan = _build_plan(
        events, origin, data.skip_weekends, holidays,
        holiday_ranges, data.default_holidays, tzinfo=project_tz)
    _cpm_and_report(plan)
    ddl = _parse_project_ddl(data.ddl, plan.origin)
    _validate_enforcement(
        data.capability_mode, data.deadline_mode, ddl)
    if wsid:
        target_wsid = wsid
    else:
        workspace = (
            _workspace_or_404(data.wsid) if data.wsid
            else store.get_or_create_default_workspace()
        )
        target_wsid = workspace.wsid
    worker_mode, worker_count, single_worker_id, active_worker_ids = (
        _normalize_worker_settings(
            data.worker_mode, data.worker_count,
            data.single_worker_id, data.active_worker_ids))
    return Project(
        prid=data.prid or _new_prid(),
        title=data.title or "Untitled Project",
        wsid=target_wsid,
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
        timezone_mode=timezone_mode,
        timezone=timezone_name,
        utc_offset_minutes=utc_offset_minutes,
        skip_weekends=data.skip_weekends,
        holidays=holidays,
        holiday_ranges=holiday_ranges,
        default_holidays=data.default_holidays,
    )


@app.post("/projects", status_code=201)
def create_project(data: ProjectCreateIn, request: Request):
    """Create a project, optionally inside a workspace.

    Without ``wsid`` the project is placed in the default workspace so the
    existing single-project frontend keeps working.
    """
    project = _build_project_from_in(data)
    _require_workspace(request, project.wsid, "editor")
    persisted = store.create_project(project)
    return _project_payload(persisted)


@app.get("/projects")
def list_projects(request: Request, wsid: Optional[str] = None):
    """List projects, optionally filtered by workspace."""
    user = auth.require_user(request)
    if wsid is not None:
        _require_workspace(request, wsid, "viewer")
    projects = store.list_projects(wsid=wsid)
    if not user.get("is_admin"):
        allowed = set(store.workspace_ids_for_user(user["id"]))
        projects = [p for p in projects if p.wsid in allowed]

    summaries = []
    for project in projects:
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
            "timezone_mode": project.timezone_mode,
            "timezone": project.timezone,
            "utc_offset_minutes": project.utc_offset_minutes,
            "skip_weekends": project.skip_weekends,
            "holidays": list(project.holidays or []),
            "holiday_ranges": list(project.holiday_ranges or []),
            "default_holidays": project.default_holidays,
            "holiday_coverage": holiday_coverage(),
            "version": project.version,
            "event_count": len(plan.events),
            "makespan": report["makespan"],
            "makespan_human": report["makespan_human"],
            "created_at": _iso_utc(project.created_at),
            "updated_at": _iso_utc(project.updated_at),
        })
    return summaries


@app.get("/projects/{prid}")
def get_project(prid: str, request: Request):
    return _project_payload(_require_project(request, prid, "viewer"))


@app.put("/projects/{prid}")
def update_project(prid: str, data: ProjectUpdateIn, request: Request):
    """Update project metadata and/or events."""
    existing = _require_project(request, prid, "editor")
    if data.version != existing.version:
        raise HTTPException(
            status_code=409,
            detail=(
                "version conflict: project was changed by another session "
                f"(expected {data.version}, current {existing.version})"))
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

    timezone_mode, timezone_name, utc_offset_minutes = _normalize_timezone(
        data.timezone_mode
        if data.timezone_mode is not None else existing.timezone_mode,
        data.timezone
        if data.timezone is not None else existing.timezone,
        data.utc_offset_minutes
        if data.utc_offset_minutes is not None
        else existing.utc_offset_minutes)
    project_tz = _tzinfo(
        timezone_mode, timezone_name, utc_offset_minutes)
    timezone_changed = (
        timezone_mode != existing.timezone_mode
        or timezone_name != existing.timezone
        or utc_offset_minutes != existing.utc_offset_minutes)

    if events_provided:
        events = data.events or []
        origin = _resolve_origin(
            fields.get("origin") if "origin" in fields else None,
            events,
            fallback=existing.origin,
        )
        plan = _build_plan(
            events, origin, skip_weekends, holidays,
            holiday_ranges, default_holidays, tzinfo=project_tz)
        project_events = list(plan.events)
    else:
        project_events = list(existing.events or [])
        if timezone_changed:
            for event in project_events:
                event.start = _reinterpret_wall(event.start, project_tz)
                event.deadline = _reinterpret_wall(
                    event.deadline, project_tz)
        if "origin" in fields and fields["origin"]:
            origin = _parse_datetime(fields["origin"], "origin")
        else:
            origin = existing.resolved_origin()
            if timezone_changed:
                origin = _reinterpret_wall(origin, project_tz)
        try:
            plan = Plan(
                project_events, origin,
                skip_weekends=skip_weekends, holidays=holidays,
                holiday_ranges=holiday_ranges,
                default_holidays=default_holidays,
                timezone=project_tz)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "ddl" in fields:
        ddl = _parse_project_ddl(fields["ddl"], plan.origin)
    else:
        ddl = existing.ddl
        if ddl is not None and timezone_changed:
            ddl = _reinterpret_wall(ddl, project_tz)
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
        _require_workspace(request, fields["wsid"], "editor")
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
        timezone_mode=timezone_mode,
        timezone=timezone_name,
        utc_offset_minutes=utc_offset_minutes,
        skip_weekends=skip_weekends,
        holidays=holidays,
        holiday_ranges=holiday_ranges,
        default_holidays=default_holidays,
    )
    persisted = store.update_project(project, data.version)
    if persisted is None:
        raise HTTPException(
            status_code=409,
            detail="version conflict: project was changed by another session")
    return _project_payload(persisted)


@app.delete("/projects/{prid}", status_code=204)
def delete_project(prid: str):
    if not store.delete_project(prid):
        raise HTTPException(
            status_code=404, detail=f"project not found: {prid}")
    return None


@app.post("/projects/{prid}/revisions", status_code=201)
def create_project_revision(prid: str, data: ProjectVersionCreateIn,
                            request: Request):
    project = _require_project(request, prid, "editor")
    label = (data.label or "").strip()
    if not label:
        label = f"Checkpoint {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    store.record_revision(project, label)
    entry = next(
        (item for item in store.list_revisions(prid)
         if item["label"] == label), None)
    return entry or {"label": label}


@app.patch("/projects/{prid}/revisions/{revision_id}")
def update_project_revision(prid: str, revision_id: int,
                            data: ProjectVersionUpdateIn, request: Request):
    _require_project(request, prid, "editor")
    label = data.label.strip()
    if not label:
        raise HTTPException(
            status_code=400, detail="version label must not be empty")
    if not store.update_revision_label(prid, revision_id, label):
        raise HTTPException(
            status_code=404, detail=f"revision not found: {revision_id}")
    return {"id": revision_id, "label": label}


@app.delete("/projects/{prid}/revisions/{revision_id}", status_code=204)
def delete_project_revision(prid: str, revision_id: int,
                            request: Request):
    _require_project(request, prid, "editor")
    if not store.delete_revision(prid, revision_id):
        raise HTTPException(
            status_code=404, detail=f"revision not found: {revision_id}")
    return None


@app.get("/projects/{prid}/revisions")
def get_project_revisions(prid: str, request: Request):
    _require_project(request, prid, "viewer")
    return store.list_revisions(prid)


@app.post("/projects/{prid}/restore")
def restore_project_revision(prid: str, data: ProjectRestoreIn,
                             request: Request):
    existing = _require_project(request, prid, "editor")
    if data.version != existing.version:
        raise HTTPException(
            status_code=409,
            detail=(
                "version conflict: project was changed by another session "
                f"(expected {data.version}, current {existing.version})"))

    snapshot = store.get_revision(prid, data.revision_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"revision not found: {data.revision_id}")

    restored = store.project_from_snapshot(snapshot, prid)
    # Keep the project in its current workspace; restore content/settings only.
    restored.wsid = existing.wsid
    persisted = store.update_project(restored, data.version)
    if persisted is None:
        raise HTTPException(
            status_code=409,
            detail="version conflict: project was changed by another session")
    return _project_payload(persisted)


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
