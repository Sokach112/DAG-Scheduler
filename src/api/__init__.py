"""HTTP API for dag-scheduler. Requires the [api] extra."""

try:
    from .app import app
    from .store import PlanSession, put, get, delete, list_sessions
    __all__ = ["app", "PlanSession", "put", "get", "delete", "list_sessions"]
except ImportError as exc:
    raise ImportError(
        "api requires FastAPI. Install with: pip install dag-scheduler[api]"
    ) from exc
