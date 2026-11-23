# DAG Scheduler

**Author: Limitless**

An end-to-end, full-stack DAG scheduling platform with Critical Path Method (CPM),
resource-constrained scheduling, a workspace/project hierarchy, and an interactive
visual console.

The project consists of a pure-Python scheduling engine, a FastAPI + SQLite backend,
and a Vue 3 + Tailwind CSS frontend for managing workspaces, projects, dependencies,
and task timelines.

## Features

### Workspace system

- Flat two-level hierarchy: **Workspace → Project**.
- Workspaces store only metadata; scheduling data lives on projects.
- Sidebar navigator lists all workspaces and expands the active workspace's projects.
- Create, rename, and delete workspaces from the sidebar.
- Deleting a workspace cascades to all projects inside it.
- Project count per workspace.
- Projects can be moved between workspaces via a typed/selectable workspace
  combobox in the project dashboard and the Edit Project modal.
- Unknown workspace names are rejected with a red **“Workspace not found”** warning.
- Deep-link routing: `?wsid=<workspace-id>` and `?wsid=<workspace-id>&prid=<project-id>`.

### Projects

- Create, rename, edit, and delete projects.
- Per-project start date (`origin`) and target date (`ddl`).
- Auto-save: task changes are persisted through project updates.
- Project-scoped CPM report, Gantt data, resource schedule, and dependency graph.
- Dashboard with project list, last-updated timestamps, and batch deletion.
- Optional default workspace for projects created without a `wsid`.

### Scheduling engine

- **CPM**: earliest/latest start and finish (`est`/`eft`/`lst`/`lft`), slack,
  critical path, and makespan.
- **Resource-constrained scheduling**: list scheduling with N workers.
- **Worker modes in the UI**: Infinite, Single (1 worker), or Custom N workers.
- **Overdue analysis**: CPM deadline violations plus resource-schedule finish
  times in finite-worker mode.
- **Graph exports**: Mermaid flowchart and Graphviz DOT.
- **What-if analysis** for changing one event's duration.

### Persistence

- Workspaces and projects are stored in **SQLite** using **SQLAlchemy**.
- Project events are stored as JSON; CPM outputs and reports are recomputed on demand.
- Automatic schema migration for the early integer-id schema and for
  pre-workspace project tables.
- Database path configurable with `DAG_SCHEDULER_DB`.
- Docker Compose mounts a named volume so data survives container recreation.

### Frontend

- Sidebar-based workspace/project navigator with CRUD actions and hover controls.
- Workspace dashboard and project editor views.
- Custom Gantt chart with critical/overdue coloring and worker rows.
- Mermaid dependency graph.
- Task editor with description, details, duration (d/h/m), start time, deadline,
  and dependency checklists.
- Mode-aware header statistics: Makespan, Critical, and Overdue.
- Workspace combobox with type-to-filter, keyboard navigation, validation, and
  red warnings for unknown names.
- URL routing and browser back/forward support.

## Architecture & Tech Stack

- **Backend / engine**: Python 3.10+, FastAPI, SQLAlchemy, SQLite, Pydantic.
- **Frontend**: Vue 3 (Composition API), Vite, Tailwind CSS, Lucide icons, Mermaid.js.
- **Topological sorting**: [graphxlib](https://pypi.org/project/graphxlib/).

### Data model

```text
Workspace 1 ─── * Project 1 ─── * Event
```

| Model | Fields |
|---|---|
| `Workspace` | `wsid`, `name`, `description`, `created_at` |
| `Project` | `prid`, `wsid`, `title`, `description`, `origin`, `ddl`, `events`, `created_at`, `updated_at` |
| `Event` | `eid`, `description`, `details`, `duration`, `priority`, `start`, `deadline`, `dependencies`, CPM fields |

- `origin` is the scheduling time base. Every CPM offset is an integer number of
  minutes relative to it.
- `ddl` is the project-level target date. It is persisted, displayed, and used
  as the project span on the Gantt; global project-deadline overdue evaluation is
  reserved for a future iteration.
- Project `report` is derived data and is never persisted.
- `origin` and `ddl` are stored as ISO-8601 strings so timezone offsets are preserved
  in SQLite.

## Project Structure

```text
DAG-Scheduler/
├── src/
│   ├── dag_scheduler/          # Pure scheduling engine
│   │   ├── models.py           # Event
│   │   ├── plan.py             # Plan origin/time-coordinate validation
│   │   ├── cpm.py              # Critical Path Method
│   │   ├── parallel.py         # Resource-constrained scheduler
│   │   ├── analysis.py         # Reports, Gantt data, Mermaid/DOT exports
│   │   ├── project.py          # Project domain model
│   │   ├── workspace.py        # Workspace domain model
│   │   └── serializer.py       # Versioned JSON I/O
│   └── api/
│       ├── app.py              # FastAPI routes
│       ├── db.py               # SQLAlchemy models, migrations, SQLite setup
│       └── store.py            # Workspace/project persistence helpers
├── frontend/
│   └── src/
│       ├── App.vue             # Sidebar layout, routing, editor/dashboard state
│       └── components/
│           ├── Sidebar.vue
│           ├── DashboardView.vue
│           ├── ProjectModal.vue
│           ├── WorkspaceModal.vue
│           ├── WorkspaceSelect.vue
│           ├── WorkspacePicker.vue
│           ├── TaskSidebar.vue
│           ├── TaskModal.vue
│           ├── GanttView.vue
│           ├── DependencyView.vue
│           └── WorkerModeSelector.vue
└── tests/                      # Pytest suite
```

## Getting Started

### 1. Backend

```bash
git clone https://github.com/Sokach112/DAG-Scheduler.git
cd DAG-Scheduler

python -m venv .venv
source .venv/bin/activate

pip install -e ".[api]"
uvicorn api.app:app --reload
```

The API runs at `http://127.0.0.1:8000`; Swagger UI is at
`http://127.0.0.1:8000/docs`.

By default the SQLite database is created at `src/api/scheduler.db`. To use a
different location:

```bash
DAG_SCHEDULER_DB=/path/to/dag_scheduler.db uvicorn api.app:app --reload
```

### 2. Frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5173`. Vite proxies `/api/*` to the backend at
`http://127.0.0.1:8000`, so the frontend calls paths such as `/api/workspaces`
and `/api/projects`.

For a production bundle:

```bash
npm run build
```

### 3. Tests

```bash
pip install pytest pytest-timeout httpx
pytest -q
```

Backend tests run against a temporary SQLite database and do not modify the
development database.

## Usage

1. **Create a workspace** with the `+` next to *Workspaces*.
2. **Create a project** in the active workspace with the `+` next to *Projects*
   or the dashboard's **New Project** button.
3. **Add tasks** with durations, start times, deadlines, priorities, and dependencies.
4. **Choose a worker mode** (Infinite, Single, or Custom N) in the editor header.
5. **Visualize** the Gantt timeline or Mermaid dependency graph.
6. **Move a project** by opening the Workspace combobox on the dashboard or in
   Edit Project and typing/selecting another workspace.

The URL reflects the active selection:

```text
/?wsid=<workspace-id>                   workspace dashboard
/?wsid=<workspace-id>&prid=<project-id> project editor
```

## API Reference

These are the backend paths. Through the Vite dev proxy they are called with an
`/api` prefix, e.g. `/api/workspaces`.

### Workspaces

| Method | Path | Description |
|---|---|---|
| GET | `/workspaces` | List workspaces with `project_count` |
| POST | `/workspaces` | Create a workspace (`name` required) |
| GET | `/workspaces/{wsid}` | Get one workspace |
| PUT | `/workspaces/{wsid}` | Update name/description |
| DELETE | `/workspaces/{wsid}` | Delete workspace and cascade its projects |

### Projects

| Method | Path | Description |
|---|---|---|
| GET | `/projects?wsid=<wsid>` | List projects, optionally filtered by workspace |
| POST | `/projects` | Create a project; optional `wsid` defaults to the default workspace |
| GET | `/projects/{prid}` | Get project, events, and computed report |
| PUT | `/projects/{prid}` | Update metadata/events and/or move to another `wsid` |
| DELETE | `/projects/{prid}` | Delete a project |
| GET | `/projects/{prid}/report` | Project CPM/overdue report |
| GET | `/projects/{prid}/gantt` | Project Gantt rows |
| GET | `/projects/{prid}/schedule?workers=N` | Resource-constrained schedule |
| GET | `/projects/{prid}/graph?format=mermaid\|dot` | Dependency graph export |

Example: create a workspace and project.

```bash
curl -X POST http://127.0.0.1:8000/workspaces \
  -H 'Content-Type: application/json' \
  -d '{"name": "Engineering", "description": "Team workspace"}'

curl -X POST http://127.0.0.1:8000/projects \
  -H 'Content-Type: application/json' \
  -d '{
    "wsid": "<wsid>",
    "title": "Website Redesign",
    "origin": "2026-11-23T00:00:00+08:00",
    "ddl": "2026-12-01T18:00:00+08:00",
    "events": []
  }'
```

Example: move a project to another workspace.

```bash
curl -X PUT http://127.0.0.1:8000/projects/<prid> \
  -H 'Content-Type: application/json' \
  -d '{"wsid": "<target-wsid>"}'
```

The target workspace is validated; an unknown `wsid` returns `404`.

### Transient plan API

The original stateless endpoints remain available for direct calculations and
experimentation. They are backed by an in-memory plan session store.

| Method | Path |
|---|---|
| POST | `/plan` |
| GET | `/plans` |
| GET/DELETE | `/plan/{plan_id}` |
| GET | `/plan/{plan_id}/gantt` |
| GET | `/plan/{plan_id}/report` |
| GET | `/plan/{plan_id}/schedule?workers=N` |
| GET | `/plan/{plan_id}/graph?format=mermaid\|dot` |
| POST | `/plan/{plan_id}/what-if` |

### Error format

HTTP errors are returned as:

```json
{"error": {"status": 400, "detail": "..."}}
```

Validation errors (`422`) keep the structured Pydantic detail list.

## Docker

The Docker image runs the backend API with SQLite on a persistent volume.

```bash
docker compose up -d
docker compose logs -f api
```

```bash
docker compose down
```

The compose file sets:

```text
DAG_SCHEDULER_DB=/app/data/scheduler.db
```

and mounts the named volume `dag-scheduler-data` at `/app/data`. The frontend is
developed/served separately with Vite (or a static host after `npm run build`).

## Known Limitations

- **Move via combobox only**: drag-and-drop of projects between workspaces is not implemented.
- **Single resource type**: workers only; no per-resource capacities or calendars.
- **No authentication**: workspaces/projects are not user-isolated yet.
- **SQLite / single worker**: the API assumes one process; the in-memory `/plan`
  handles are not shared across workers.
- **Project-level deadline**: stored and displayed, but overdue currently uses
  task deadlines (and resource finish times in finite-worker mode), not the
  project-wide `ddl`.
- **CPM critical path**: when several critical chains exist, `critical_path`
  returns one deterministic chain. Use `critical_events` for the full set.

## Roadmap

- User accounts, authentication, and per-user workspace isolation.
- Drag-and-drop project movement.
- Project-wide deadline overdue evaluation.
- Multi-resource scheduling with capacities and working calendars.
- Shared production database for multi-worker API deployment.

## License

This project is licensed under the MIT License.
