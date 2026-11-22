# DAG Scheduler

**Author: Limitless**

An end-to-end, full-stack DAG scheduling platform with Critical Path Method (CPM), resource-constrained scheduling, and a modern interactive visual console.

This project consists of a robust Python scheduling engine, a FastAPI backend with SQLite persistence, and a Vue 3 + Tailwind CSS frontend for visualizing dependencies and task timelines.

## Features

- **Core Scheduling Engine (`dag_scheduler`)**
  - **CPM Analysis**: Compute Earliest Start/Finish (`est`/`eft`), Latest Start/Finish (`lst`/`lft`), slack, and identify the critical path.
  - **Resource-Constrained Scheduling**: Simulate multiple workers (Infinite, Single, or Custom N workers) to find the optimal makespan.
  - **Flexible Time Handling**: Support for absolute datetime, integer minute offsets, and hard constraints.
- **Data Persistence**
  - Multi-project management backed by **SQLite** and **SQLAlchemy**.
  - Auto-save functionality; never lose your plan.
- **Visual Console (Frontend)**
  - **Dashboard**: Manage multiple projects (Create, Edit, Delete, Batch Delete).
  - **Interactive Gantt**: Custom-built Gantt charts showing task overlaps, worker assignments, and critical paths.
  - **Dependency Graph**: Auto-generated Mermaid.js DAG graphs.
  - **Rich Forms**: Smart duration parsing (e.g., "1d 2h 30m"), time pickers, and dependency checklists.

##  Architecture & Tech Stack

- **Backend / Engine**: Python 3.10+, FastAPI, SQLAlchemy, SQLite, Pydantic.
- **Frontend**: Vue 3 (Composition API), Vite, Tailwind CSS, Lucide Icons, Mermaid.js.
- **Core Algorithm Dependency**: [graphxlib](https://pypi.org/project/graphxlib/) (for DAG topological sorting).

```text
DAG-Scheduler/
├── src/
│   ├── dag_scheduler/    # Pure Python scheduling engine (CPM, Serializer, Parallel)
│   └── api/              # FastAPI routes & SQLite database models
├── frontend/             # Vue 3 + Vite single-page application
│   ├── src/components/   # Reusable UI (GanttView, TaskModal, etc.)
│   └── src/App.vue       # Main routing and global state
└── tests/                # Pytest suite for backend logic
```

## Getting Started

### 1. Backend Setup

We recommend using a virtual environment.

```bash
# Clone the repository
git clone https://github.com/Sokach112/DAG-Scheduler.git
cd DAG-Scheduler

# Install dependencies
pip install -e ".[api,dev]"

# Start the FastAPI server
uvicorn api.app:app --reload
```
The backend will run at `http://127.0.0.1:8000`. You can view the Swagger UI at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

Open a new terminal window:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
The frontend will be available at `http://localhost:5173`. Vite is configured to proxy `/api` requests to the FastAPI backend.

## How it Works

1. **Projects**: Create a project with a global time span (Origin to Deadline).
2. **Tasks**: Add tasks with a duration (supports "2h 30m" syntax), priority, and dependencies.
3. **Run**: The Vue frontend serializes the plan and sends it to FastAPI.
4. **Analyze**: FastAPI uses `CPMScheduler` to calculate the critical path and `ParallelScheduler` to simulate resource constraints.
5. **Visualize**: The results are sent back and rendered as custom Gantt bars and Mermaid DAG graphs.



## License

This project is licensed under the MIT License.