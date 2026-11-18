"""FastAPI application for dag-scheduler."""

from uuid import uuid4
from datetime import datetime, timezone
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dag_scheduler.analysis import _status

from dag_scheduler import (
    CPMScheduler,
    plan_from_dict, plan_to_dict,
    gantt_data, feasibility_report,
    to_mermaid, to_dot,
)
from dag_scheduler.analysis import (
    gantt_data, feasibility_report, what_if,
    to_mermaid, to_dot,
)
from dag_scheduler.parallel import ParallelScheduler
from dag_scheduler.serializer import SerializationError

from . import store

app = FastAPI(title="DAG Scheduler API")
app.mount("/web", StaticFiles(directory="web", html=True), name="web")

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
    duration: int
    priority: int
    start: str
    deadline: str
    dependencies: list[str] = []


class PlanIn(BaseModel):
    version: int = 1
    origin: str
    events: list[EventIn]


# ---------- helpers ----------
def _session_or_404(plan_id: str) -> store.PlanSession:
    session = store.get(plan_id)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"plan not found: {plan_id}")
    return session


# ---------- endpoints ----------
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
        ],
    }


@app.post("/plan")
def create_plan(data: PlanIn):
    """Create a plan from JSON and immediately run CPM."""
    try:
        plan = plan_from_dict(data.model_dump())
        cpm = CPMScheduler(plan).run()
    except (SerializationError, ValueError) as exc:
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
    rep = feasibility_report(session.plan, session.cpm)
    return {
        "event_count": rep.event_count,
        "makespan": rep.makespan,
        "makespan_human": rep.makespan_human,
        "critical_count": rep.critical_count,
        "overdue_count": rep.overdue_count,
        "overdue": rep.overdue,
        "is_feasible": rep.is_feasible,
        "max_concurrency": session.cpm.max_concurrency,  # 👈 新增这一行
    }


@app.get("/plan/{plan_id}/schedule")
def get_schedule(plan_id: str, workers: int = 1):
    """Resource-constrained schedule with the given number of workers."""
    session = _session_or_404(plan_id)
    if workers < 1:
        raise HTTPException(status_code=400, detail="workers must be >= 1")

    result = ParallelScheduler(session.plan, workers).run()
    tasks_info = {}
    for e in session.plan.events:
        tasks_info[e.eid] = {
            "description": e.description,
            "priority": e.priority,
            "status": _status(e),
        }

    return {
        "makespan": result.makespan,
        "workers": result.workers,
        "start": result.start,
        "end": result.end,
        "assignments": result.assignments,
        "tasks": tasks_info,
    }


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
