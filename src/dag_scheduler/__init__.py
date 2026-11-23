"""DAG-based task scheduler with CPM and resource-constrained scheduling."""

from .models import Event
from .helper import SchedulerHelper, EventFactory, CycleError, DuplicateIDError
from .plan import Plan
from .cpm import CPMScheduler, CPMResult
from .analysis import (
    gantt_data,
    deadline_violations,
    feasibility_report,
    FeasibilityReport,
    critical_width_estimate,
    render_gantt_text,
    to_dot,
    to_mermaid,
)
from .parallel import ParallelScheduler, ResourceScheduleResult
from .serializer import (
    plan_to_dict, plan_from_dict,
    events_to_dict,
    save_to_json, load_from_json,
    SerializationError,
)
from .project import Project, DEFAULT_ORIGIN
from .workspace import Workspace
from .worker import Worker

__all__ = [
    "Event", "SchedulerHelper", "EventFactory",
    "CycleError", "DuplicateIDError",
    "Plan", "CPMScheduler", "CPMResult",
    "gantt_data", "deadline_violations", "feasibility_report",
    "FeasibilityReport", "critical_width_estimate",
    "render_gantt_text", "to_dot", "to_mermaid",
    "ParallelScheduler", "ResourceScheduleResult", 
    "plan_to_dict", "plan_from_dict",
    "events_to_dict",
    "save_to_json", "load_from_json",
    "SerializationError",
    "Project", "DEFAULT_ORIGIN", "Workspace", "Worker",
]
