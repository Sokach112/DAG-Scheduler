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
- Optimistic concurrency: every project has a version; stale updates receive
  `409 Conflict`.
- **Field-level merge**: on a conflict, the editor merges non-overlapping project
  fields and task fields, lets the user choose mine/theirs per conflict, or
  overwrite with local changes.
- **Durable undo/redo**: left/right arrow buttons (and `Ctrl/Cmd+Z`,
  `Ctrl/Cmd+Shift+Z`, `Ctrl/Cmd+Y`) walk up to 20 edits. The queue is stored in
  the browser per project, so it survives reloads and project switches.
- **Manual checkpoints**: the save icon snapshots the current project as a named
  checkpoint. Checkpoints are only created manually; edits auto-save. The
  Checkpoints modal shows names only (no version numbers), supports rename in a
  dialog, delete, restore, and keeps the 10 most recent checkpoints.
- **Project / workspace import-export**: export a project as JSON or a workspace
  as a ZIP of project JSON files; import either back with new local IDs.
- Project-scoped CPM report, Gantt data, resource schedule, and dependency graph.
- Dashboard with project list, last-updated timestamps, and batch deletion.
- Optional default workspace for projects created without a `wsid`.
- Project-level named team roster with stable worker IDs; renaming a worker
  preserves existing task capabilities.

### Scheduling engine

- **CPM**: earliest/latest start and finish (`est`/`eft`/`lst`/`lft`), slack,
  critical path, and makespan.
- **Resource-constrained scheduling**: capability-aware list scheduling.
- **Load-balanced assignment**: each task goes to the least-loaded capable free
  worker, so an idle team member is used before adding more work to a busy one.
- **Per-project timezone**: choose a named IANA zone (DST-aware) or a fixed
  UTC offset in 15-minute steps (UTC−10:00 … UTC+14:00). Project inputs,
  calendar day boundaries, Gantt labels, holidays, and deadlines use it.
- **Working calendar**: projects can skip weekends, custom holiday **date ranges**,
  or use the built-in China statutory calendar (2025–2027 official schedules, including
  make-up workdays). CPM, resource scheduling, dependencies, Gantt times, and
  deadlines all use the same calendar. Weekdays are currently full working days.
- **Holiday data coverage metadata**: the API exposes which years/regions have
  statutory data; projects beyond coverage show a warning instead of silently
  pretending statutory holidays are applied.
- **Workers N mode (quick prototype)**: N generic workers, no names. Tasks can
  restrict themselves to specific generic slots (`Worker 0`, `Worker 1`, ...).
- **Team mode (named roster)**: each project can define a named roster; tasks
  list the team members capable of doing them. An empty capability list means
  every active worker.
- **Active team members**: in Team mode choose which roster members are active
  for this scheduling run; names remain saved when they are marked inactive.
- **Both capability sets are independent**: Team capabilities use stable worker
  IDs, Workers N capabilities use worker indices. Switching modes does not
  erase the other configuration.
- **Per-project mode settings**: each project remembers whether it uses
  Infinite, Single, Workers N, or Team, plus its generic count; switching
  projects restores that project's configuration.
- **Team roster is optional and persistent**: switching Team → Workers N → Team
  keeps the saved names.
- **Capability enforcement**: projects choose `fallback` (assign an active
  worker anyway, with a warning) or `strict` (reject the schedule and list the
  tasks that no active worker can perform).
- **Project deadline enforcement**: `soft` shows a warning when the schedule
  finishes after `ddl`; `hard` marks the project infeasible and reports the
  violation. The best-effort timeline is still shown for diagnosis.
- **Overdue analysis**: task deadlines plus the project-wide `ddl`. A task is
  late when its CPM/resource finish exceeds the earlier of its task deadline and
  the project deadline; the report/banner also flags a late project finish.
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
- **Drag-and-drop**: drag a project row in the sidebar onto another workspace
  to move it.
- **Enter to save**: press Enter in a modal form to save (Cmd/Ctrl+Enter from
  multiline textareas).
- **Dashboard** shortcut in the sidebar opens the global Home page with workspace cards.
- Workspace dashboard and project editor views.
- Custom Gantt chart with critical/overdue coloring and named worker rows.
- Mermaid dependency graph.
- Task editor with description, details, duration (d/h/m), start time, deadline,
  dependency checklists, and capable-worker checkboxes (inactive team members
  are marked).
- Team editor includes an **Active** toggle per member; active choices persist
  per project.
- **Edit team** button appears only in Team mode; the roster editor is opened
  from there, so Workers N/Infinite/Single stay uncluttered.
- Team editor for adding, renaming, and removing named workers; names persist
  across mode switches.
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
                    │
                    └── * Worker (named team roster)
```

| Model | Fields |
|---|---|
| `Workspace` | `wsid`, `name`, `description`, `created_at` |
| `Project` | `prid`, `wsid`, `title`, `description`, `origin`, `ddl`, `events`, `workers`, `worker_mode`, `worker_count`, `active_worker_ids`, `capability_mode`, `deadline_mode`, `timezone_mode`, `timezone`, `utc_offset_minutes`, `skip_weekends`, `holidays`, `holiday_ranges`, `default_holidays`, `version`, `created_at`, `updated_at` |
| `Worker` | `wid` (stable id), `name` |
| `Event` | `eid`, `description`, `details`, `duration`, `priority`, `start`, `deadline`, `dependencies`, `capable_workers`, `capable_workers_generic`, CPM fields |

- `origin` is the scheduling time base. Every CPM offset is an integer number of
  minutes relative to it.
- `ddl` is the project-level target date. It is persisted, displayed, used as
  the project span on the Gantt, and evaluated as a project-wide overdue deadline.
- Project `report` is derived data and is never persisted.
- `origin` and `ddl` are stored as ISO-8601 strings so timezone offsets are preserved
  in SQLite.
- `Worker.wid` is stable across renames. `Event.capable_workers` stores Team
  worker ids; `Event.capable_workers_generic` stores Workers N indices. An empty
  list in either field means every active worker in that mode is allowed.
- Project workers are persisted as JSON alongside the event JSON.
- Per-project worker settings are persisted on the project: `worker_mode`
  (`infinite`/`1`/`workers`/`team`), `worker_count`, `active_worker_ids`,
  `capability_mode` (`fallback`/`strict`), `deadline_mode` (`soft`/`hard`),
  `skip_weekends`, legacy `holidays` dates, `holiday_ranges` periods,
  `default_holidays`, and the timezone configuration. Switching projects
  restores that project's configuration.

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
│   │   ├── worker.py           # Named team member
│   │   ├── work_calendar.py    # Weekend/holiday working-day calendar
│   │   ├── default_holidays.py # Versioned holiday dataset loader
│   │   └── data/holidays/cn/   # 2025-2027 official China schedules (JSON)
│   │   └── serializer.py       # Versioned JSON I/O
│   └── api/
│       ├── app.py              # FastAPI routes
│       ├── db.py               # SQLAlchemy models, migrations, SQLite setup
│       └── store.py            # Workspace/project persistence helpers
├── frontend/
│   └── src/
│       ├── App.vue             # Sidebar layout, routing, editor/dashboard state
│       ├── utils/
│       │   ├── keyboard.ts     # Enter-to-save rule
│       │   └── timezone.ts     # IANA/fixed-offset conversion helpers
│       └── components/
│           ├── Sidebar.vue
│           ├── HomeView.vue
│           ├── DashboardView.vue
│           ├── ProjectModal.vue
│           ├── TeamModal.vue
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
3. **Choose a worker mode** in the editor header:
   - **Infinite** ignores resource limits.
   - **Single** schedules on one generic worker.
   - **Workers N** schedules on N generic workers, for quick prototypes.
   - **Team** schedules using the project's named roster.
   The mode and N are saved **per project**.
4. **In Team mode**, click **Edit team** to add names such as Alice, Bob, and
   Carol. Each name gets a stable worker ID. Use the **Active** checkbox to
   choose who is available this run; switching modes keeps both the roster and
   the active subset.
5. **Add tasks** with durations, start times, deadlines, and dependencies.
   - In Team mode, the task editor shows named **Capable workers**.
   - In Workers N/Single mode, it shows `Worker 0..N-1` checkboxes.
   Leaving all unchecked means every active worker can do the task. The two
   capability sets are stored independently.
6. **Configure enforcement** from Project Settings:
   - Capabilities: `Fallback` or `Strict`.
   - Project deadline: `Soft` (warn) or `Hard` (infeasible).
7. **Choose the project timezone** from Project Settings: a named IANA zone
   (DST-aware) or a fixed UTC offset in 15-minute steps. Date inputs and Gantt
   labels use that project timezone, not the browser timezone.
8. **Optional working calendar**: enable **Skip weekends and holidays**, then
   add custom holiday **periods** (start/end) or enable **Use default holidays
   (China statutory, 2025–2027)**. Task durations and dependencies only advance
   through working days; official make-up workdays are honored.
6. **Visualize** the Gantt timeline with named worker rows or the Mermaid
   dependency graph.
7. **Move a project** by dragging its sidebar row onto another workspace, or by
   using the Workspace combobox on the dashboard/Edit Project.

The URL reflects the active selection:

```text
/                                       home (all workspaces)
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
| GET | `/projects/{prid}` | Get project, events, team roster, and computed report |
| PUT | `/projects/{prid}` | Update project; requires the current `version` (stale writes return 409) |
| DELETE | `/projects/{prid}` | Delete a project |
| GET | `/projects/{prid}/report` | Project CPM/overdue report |
| GET | `/projects/{prid}/gantt` | Project Gantt rows |
| GET | `/projects/{prid}/schedule?workers=N` | Workers N schedule using generic capabilities |
| GET | `/projects/{prid}/schedule?worker_ids=alice,bob` | Team schedule using named capabilities |
| GET | `/projects/{prid}/graph?format=mermaid\|dot` | Dependency graph export |
| GET | `/projects/{prid}/revisions` | List saved checkpoints (name-only metadata) |
| POST | `/projects/{prid}/revisions` | Save the current project as a checkpoint |
| PATCH | `/projects/{prid}/revisions/{revision_id}` | Rename a checkpoint |
| DELETE | `/projects/{prid}/revisions/{revision_id}` | Delete a checkpoint |
| POST | `/projects/{prid}/restore` | Restore a checkpoint using the current project version |
| GET | `/projects/{prid}/export` | Download project JSON |
| POST | `/projects/import?wsid=<wsid>` | Import project JSON into a workspace |
| GET | `/workspaces/{wsid}/export` | Download workspace ZIP |
| POST | `/workspaces/import` | Import workspace ZIP |
| GET | `/holidays/coverage` | Statutory holiday coverage (region, years, sources) |

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
    "workers": [
      {"wid": "alice", "name": "Alice"},
      {"wid": "bob", "name": "Bob"}
    ],
    "worker_mode": "team",
    "worker_count": 2,
    "events": [
      {
        "eid": "T1",
        "description": "Frontend Development",
        "duration": 120,
        "priority": 1,
        "start": "2026-11-23T00:00:00+08:00",
        "deadline": "2026-11-23T23:59:00+08:00",
        "dependencies": [],
        "capable_workers": ["alice"],
        "capable_workers_generic": [0]
      }
    ]
  }'
```

Example: move a project to another workspace.

```bash
curl -X PUT http://127.0.0.1:8000/projects/<prid> \
  -H 'Content-Type: application/json' \
  -d '{"wsid": "<target-wsid>", "version": 1}'
```

The target workspace is validated; an unknown `wsid` returns `404`.

Example: Workers N schedule (generic capabilities).

```bash
curl 'http://127.0.0.1:8000/projects/<prid>/schedule?workers=2'
```

Example: Team schedule (named capabilities).

```bash
curl 'http://127.0.0.1:8000/projects/<prid>/schedule?worker_ids=alice,bob'
```

If a task's capability list has no intersection with the active workers in
that mode, the response always contains a schedule and reports the eids in
`capability_fallbacks`. The Gantt displays a warning for those tasks.

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

### Scheduling

- **Heuristic, not optimal**: tasks use priority + least-loaded list scheduling.
  It spreads work, but does not guarantee the true minimum makespan.
- **Single resource type**: workers only; no machine pools, per-resource
  capacities, shifts, vacations, or working calendars.
- **Team availability is manual**: active/inactive is a project-level choice,
  not per-day availability. There are no shifts, vacations, or working hours yet.
- **Working calendar is whole-day only**: skipping weekends/holidays uses full
  working days. There are no partial shifts, lunch breaks, or per-worker
  calendars. Makespan is measured in calendar time including non-working days.
- **Default statutory data is limited**: built-in public holidays currently
  cover **China 2025–2027** (including make-up workdays). Other years/regions
  need custom ranges. Projects spanning uncovered years show an amber warning;
  no official holidays are invented for those years.
- **Calendar visuals are basic**: the Gantt does not shade weekends/holidays;
  a task spanning a weekend is drawn as one continuous bar.
- **Fallback is still the default**: use Strict mode to block unassignable
  tasks. Strict mode returns a 409 error listing the task IDs, rather than a
  partial schedule.
- **Hard deadline is a verdict, not an optimizer**: a late hard project is
  marked infeasible with a best-effort timeline; the scheduler does not
  automatically shorten tasks or move the deadline.
- **Infinite mode ignores resources**: it uses CPM only, so worker capabilities
  and finite-worker load balancing do not apply.
- **Mode-specific capabilities**: Team capabilities are stable worker IDs;
  Workers N capabilities are positional `Worker 0..N-1`. Lowering N can make a
  generic capability out of range and trigger fallback.
- **One critical chain**: when multiple critical chains exist, `critical_path`
  returns one deterministic chain; use `critical_events` for the full set.

### Collaboration & persistence

- **No authentication**: all workspaces and projects are shared by anyone who
  can reach the API; there is no per-user isolation.
- **SQLite / single process**: the API assumes one process. Transient `/plan`
  sessions live in memory and are not shared across workers.
- **Merge scope**: field-level merge is available for the open project editor.
  Dashboard-only conflicts fall back to reload. Task deletions or additions on
  both sides may still require choosing a whole task.
- **Undo queue storage**: the 20-edit queue is durable per browser/project in
  `localStorage`; it does not sync across browsers or devices, and very large
  projects may exceed browser storage quota. Checkpoints are the durable
  server-side history.
- **Checkpoint scale**: each project keeps the 10 most recent manual
  checkpoints. Older checkpoints are pruned when a new one is saved.
- **Import IDs**: imported workspaces/projects receive new local IDs; existing
  references to the old IDs are not preserved. Checkpoints are not included in
  project/workspace exports.
- **No trash**: deleting a workspace cascades to its projects, and there is no
  recovery UI.
- **Project-scoped people**: worker rosters and capabilities live on one
  project; there is no shared people directory or cross-project skill matrix.
  Removing a worker can leave task capabilities pointing at a missing ID, which
  triggers fallback.

### UI & interaction

- **Desktop-first**: the sidebar/editor layout is not optimized for small or
  touch screens.
- **Drag-and-drop is sidebar-only**: drag a project row onto another workspace
  while its source workspace is open. Dashboard rows and touch drag are not
  supported.
- **Enter-to-save scope**: Enter saves modal forms; in multiline textareas it
  inserts a newline, and `Cmd/Ctrl+Enter` saves instead.
- **Named timezone list is a preset**: the UI lists common IANA zones; other
  valid IANA names are accepted by the API but need a UI/data extension.
- **Fixed offsets have no DST**: choosing a fixed UTC offset will not adjust
  automatically for daylight saving. Use a named zone where possible.
- **DST edge inputs**: wall times that are skipped/ambiguous during a DST
  transition are resolved by the conversion helper rather than rejected.
- **English-only UI**: labels and validation messages are not localized.

## Roadmap

- User accounts, authentication, and per-user workspace isolation.
- Multi-resource scheduling with capacities, shifts, and partial working hours.
- Maintained statutory holiday datasets for more years/regions.
- Admin holiday-data import, remote manifest sync, and automated annual update
  prompts (deferred to the user-system phase).
- Shared people directory across projects with skill matrices.
- Deadline-aware/optimizing scheduling and automatic schedule repair.
- Cross-device durable undo and configurable checkpoint retention.
- Touch-friendly drag-and-drop, responsive layout, and localization.
- Shared production database for multi-worker API deployment.

## License

This project is licensed under the MIT License.
