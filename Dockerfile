FROM python:3.12-slim

WORKDIR /app

# Copy metadata first for better layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir ".[api]"

EXPOSE 8000

# Single worker: store.py is an in-memory dict, not shared across processes.
# Switch to a persistent store before increasing --workers.
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]