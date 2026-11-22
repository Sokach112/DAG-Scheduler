"""SQLite persistence model for projects.

``origin`` and ``ddl`` are stored as ISO-8601 strings on purpose: they are
timezone-aware timestamps, and SQLite's DateTime type would silently drop
the UTC offset. Event inputs are stored as JSON (see ``store.py``).
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)

from dag_scheduler.project import DEFAULT_ORIGIN


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get(
    "DAG_SCHEDULER_DB", os.path.join(BASE_DIR, "scheduler.db"))
if os.path.dirname(DB_PATH):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    """Naive UTC timestamp for the SQLite DateTime bookkeeping columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProjectModel(Base):
    __tablename__ = "projects"

    prid: Mapped[str] = mapped_column(
        String, primary_key=True, index=True,
        default=lambda: uuid.uuid4().hex[:8])
    title: Mapped[str] = mapped_column(
        String, nullable=False, index=True, default="Untitled Project")
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="")
    # ISO-8601 strings; keep the timezone offset that DateTime would lose.
    origin: Mapped[str] = mapped_column(DateTime, nullable=False)
    ddl: Mapped[Optional[str]] = mapped_column(DateTime, nullable=True)
    events_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


def _migrate_legacy_projects(conn: Connection) -> None:
    """Rebuild the early dev schema (INTEGER prid) without losing rows."""
    inspector = inspect(conn)
    if "projects" not in inspector.get_table_names():
        return

    cols = {c["name"]: c for c in inspector.get_columns("projects")}
    prid_col = cols.get("prid")
    if prid_col is None or isinstance(prid_col["type"], String):
        return

    conn.execute(text("ALTER TABLE projects RENAME TO projects_legacy"))
    # Legacy indexes keep their names after the rename and would collide with
    # the new table's indexes.
    for index in inspect(conn).get_indexes("projects_legacy"):
        name = index.get("name")
        if name:
            conn.execute(text(f'DROP INDEX IF EXISTS "{name}"'))

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
        # A string avoids SQLAlchemy's deprecated raw-SQLite datetime adapter.
        "now": _utcnow().isoformat(sep=" "),
    })
    conn.execute(text("DROP TABLE projects_legacy"))


def init_db() -> None:
    with engine.begin() as conn:
        _migrate_legacy_projects(conn)
        Base.metadata.create_all(bind=conn)


init_db()
