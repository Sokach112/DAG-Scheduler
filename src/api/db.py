"""SQLite persistence models for workspaces and projects.

The v0.2 hierarchy is flat: Workspace -> Project. Workspaces only carry
metadata; projects own the scheduling payload.

``origin`` and ``ddl`` are stored as ISO-8601 strings on purpose: they are
timezone-aware timestamps, and SQLite's DateTime type would silently drop
the UTC offset. Event inputs are stored as JSON (see ``store.py``).
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
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


def _enable_sqlite_foreign_keys(
        dbapi_connection: Any, connection_record: Any) -> None:
    """SQLite does not enforce foreign keys unless explicitly enabled."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


event.listen(engine, "connect", _enable_sqlite_foreign_keys)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    """Naive UTC timestamp for the SQLite DateTime bookkeeping columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    wsid: Mapped[str] = mapped_column(
        String, primary_key=True, index=True,
        default=lambda: uuid.uuid4().hex[:8])
    name: Mapped[str] = mapped_column(
        String, nullable=False, default="My Workspace")
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow)

    projects: Mapped[List["ProjectModel"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan")


class ProjectModel(Base):
    __tablename__ = "projects"

    prid: Mapped[str] = mapped_column(
        String, primary_key=True, index=True,
        default=lambda: uuid.uuid4().hex[:8])
    wsid: Mapped[str] = mapped_column(
        String,
        ForeignKey("workspaces.wsid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String, nullable=False, index=True, default="Untitled Project")
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="")
    # ISO-8601 strings; keep the timezone offset that DateTime would lose.
    origin: Mapped[str] = mapped_column(String, nullable=False)
    ddl: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    events_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    workspace: Mapped["WorkspaceModel"] = relationship(
        back_populates="projects")


# ---------- migration helpers ----------
def _default_workspace_id(conn: Connection) -> str:
    """Return the oldest workspace id, creating one when the table is empty."""
    row = conn.execute(text(
        "SELECT wsid FROM workspaces ORDER BY created_at LIMIT 1")).first()
    if row is not None:
        return str(row[0])

    wsid = uuid.uuid4().hex[:8]
    conn.execute(
        text(
            "INSERT INTO workspaces (wsid, name, description, created_at) "
            "VALUES (:wsid, :name, :description, :created_at)"
        ),
        {
            "wsid": wsid,
            "name": "My Workspace",
            "description": "",
            "created_at": _utcnow().isoformat(sep=" "),
        },
    )
    return wsid


def _migrate_legacy_projects(conn: Connection) -> None:
    """Rebuild the early dev schema (INTEGER prid) without losing rows."""
    # Creates the workspaces table (and projects on a fresh database).
    Base.metadata.create_all(bind=conn)

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
    default_wsid = _default_workspace_id(conn)

    updated = "updated_at" if "updated_at" in cols else ":now"
    origin = "origin" if "origin" in cols else ":default_origin"
    ddl = "ddl" if "ddl" in cols else "NULL"
    events = "events_json" if "events_json" in cols else "'[]'"
    title = "title" if "title" in cols else "'Untitled Project'"
    description = "description" if "description" in cols else "''"

    conn.execute(text(f"""
        INSERT INTO projects (
            prid, wsid, title, description, origin, ddl, events_json,
            created_at, updated_at
        )
        SELECT
            'p' || CAST(prid AS TEXT),
            :wsid,
            COALESCE({title}, 'Untitled Project'),
            COALESCE({description}, ''),
            COALESCE({origin}, :default_origin),
            {ddl},
            COALESCE({events}, '[]'),
            COALESCE({updated}, :now),
            COALESCE({updated}, :now)
        FROM projects_legacy
    """), {
        "wsid": default_wsid,
        "default_origin": DEFAULT_ORIGIN.isoformat(),
        # A string avoids SQLAlchemy's deprecated raw-SQLite datetime adapter.
        "now": _utcnow().isoformat(sep=" "),
    })
    conn.execute(text("DROP TABLE projects_legacy"))


def _add_wsid_column(conn: Connection) -> None:
    """Attach the workspace foreign key to a pre-workspace projects table."""
    inspector = inspect(conn)
    if "projects" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("projects")}
    if "wsid" in columns:
        return

    conn.execute(text("ALTER TABLE projects ADD COLUMN wsid VARCHAR"))
    if conn.execute(text("SELECT COUNT(*) FROM projects")).scalar_one():
        default_wsid = _default_workspace_id(conn)
        conn.execute(
            text("UPDATE projects SET wsid = :wsid WHERE wsid IS NULL"),
            {"wsid": default_wsid},
        )
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_projects_wsid ON projects (wsid)"))


def init_db() -> None:
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
        _migrate_legacy_projects(conn)
        _add_wsid_column(conn)


init_db()
