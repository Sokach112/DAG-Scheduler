"""HTTP API for dag-scheduler. Requires the [api] extra."""

try:
    from .app import app
    from .store import (
        PlanSession,
        put,
        get,
        delete,
        list_sessions,
        create_project,
        get_project,
        list_projects,
        update_project,
        delete_project,
        create_workspace,
        get_workspace,
        list_workspaces,
        update_workspace,
        delete_workspace,
        get_or_create_default_workspace,
    )
    from dag_scheduler.analysis import (
        gantt_data,
        deadline_violations,
        feasibility_report,
        FeasibilityReport,
        critical_width_estimate,
        render_gantt_text,
        to_dot,
        to_mermaid,
        what_if,
    )
    __all__ = ["app", 
               "PlanSession",
                 "put", 
                 "get", 
                 "delete", 
                 "list_sessions", 
                 "create_project",
                 "get_project",
                 "list_projects",
                 "update_project",
                 "delete_project",
                 "create_workspace",
                 "get_workspace",
                 "list_workspaces",
                 "update_workspace",
                 "delete_workspace",
                 "get_or_create_default_workspace",
                 "gantt_data",
                 "deadline_violations",
                 "feasibility_report",
                 "FeasibilityReport",
                 "critical_width_estimate",
                 "render_gantt_text",
                 "to_dot",
                 "to_mermaid",
                 "what_if",]

except ImportError as exc:
    raise ImportError(
        "api requires FastAPI. Install with: pip install dag-scheduler[api]"
    ) from exc
