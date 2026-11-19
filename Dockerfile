FROM python:3.12-slim

WORKDIR /app

# Copy metadata first for better layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir ".[api]"

# Projects are persisted in SQLite. Mount a volume on /app/data so the
# database survives container recreation.
ENV DAG_SCHEDULER_DB=/app/data/scheduler.db
RUN mkdir -p /app/data

EXPOSE 8000

# Single worker: the transient /plan sessions are per-process; projects
# themselves live in the shared SQLite database.
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]