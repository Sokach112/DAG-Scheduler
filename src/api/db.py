"""SQLite persistence for projects.

The database file defaults to ``src/api/scheduler.db`` and can be overridden
with the ``DAG_SCHEDULER_DB`` environment variable (the Docker setup points
it at a mounted volume).
"""

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from dag_scheduler.project import DEFAULT_ORIGIN


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get(
    "DAG_SCHEDULER_DB", os.path.join(BASE_DIR, "scheduler.db"))
if os.path.dirname(DB_PATH):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def _utcnow() -> datetime:
    """Naive UTC timestamp for SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProjectModel(Base):
    __tablename__ = "projects"

    prid = Column(String, primary_key=True)
    title = Column(String, nullable=False, default="Untitled Project")
    description = Column(Text, nullable=False, default="")
    origin = Column(String, nullable=False)
    ddl = Column(String, nullable=True)
    events_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


def _migrate_legacy_projects(conn) -> None:
    """Rebuild the early dev schema (INTEGER prid) without losing rows."""
    inspector = inspect(conn)
    if "projects" not in inspector.get_table_names():
        return

    cols = {c["name"]: c for c in inspector.get_columns("projects")}
    prid_col = cols.get("prid")
    if prid_col is None or isinstance(prid_col["type"], String):
        return

    conn.execute(text("ALTER TABLE projects RENAME TO projects_legacy"))
    Base.metadata.create_all(bind=conn)

    updated = "updated_at" if "updated_at" in cols else ":now"
    origin = "origin" if "origin" in cols else ":default_origin"
    ddl = "ddl" if "ddl" in cols else "NULL"
    events = "events_json" if "events_json" in cols else "'[]'"
    title = "title" if "title" in cols else "'Untitled Project'"
    description = "description" if "description" in cols else "''"

    conn.execute(text(f"""
        INSERT INTO projects (
            prid, title, description, origin, ddl, events_json,
            created_at, updated_at
        )
        SELECT
            'p' || CAST(prid AS TEXT),
            COALESCE({title}, 'Untitled Project'),
            COALESCE({description}, ''),
            COALESCE({origin}, :default_origin),
            {ddl},
            COALESCE({events}, '[]'),
            COALESCE({updated}, :now),
            COALESCE({updated}, :now)
        FROM projects_legacy
    """), {
        "default_origin": DEFAULT_ORIGIN.isoformat(),
        # Pass a string so raw SQLite text() does not use the deprecated
        # datetime adapter.
        "now": _utcnow().isoformat(sep=" "),
    })
    conn.execute(text("DROP TABLE projects_legacy"))


def init_db() -> None:
    with engine.begin() as conn:
        _migrate_legacy_projects(conn)
        Base.metadata.create_all(bind=conn)


init_db()
