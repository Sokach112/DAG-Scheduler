"""Tests for the workspace model, CRUD, and project ownership."""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from api import app, store
from api.db import (
    ProjectModel,
    SessionLocal,
    WorkspaceModel,
    engine,
)


TZ = datetime.timezone(datetime.timedelta(hours=8))
ORIGIN = datetime.datetime(2026, 11, 19, 9, 0, tzinfo=TZ)


def iso(minutes: int = 0) -> str:
    return (ORIGIN + datetime.timedelta(minutes=minutes)).isoformat()


def event(eid="T1", duration=60):
    return {
        "eid": eid,
        "description": f"Task {eid}",
        "details": "",
        "duration": duration,
        "priority": 1,
        "start": iso(0),
        "deadline": iso(180),
        "dependencies": [],
    }


@pytest.fixture(autouse=True)
def clean_tables():
    store._sessions.clear()

    def clear():
        with SessionLocal() as session:
            session.query(ProjectModel).delete()
            session.query(WorkspaceModel).delete()
            session.commit()

    clear()
    yield
    clear()


@pytest.fixture
def client():
    return TestClient(app)


def create_workspace(client, name="Engineering", description="Team space"):
    response = client.post(
        "/workspaces", json={"name": name, "description": description})
    assert response.status_code == 201, response.text
    return response.json()


def create_project(client, wsid=None, title="Alpha", events=None):
    payload = {
        "title": title,
        "description": "Project notes",
        "events": events if events is not None else [event()],
    }
    if wsid is not None:
        payload["wsid"] = wsid
    response = client.post("/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- schema ----------
def test_workspace_and_fk_columns_exist():
    inspector = inspect(engine)

    workspace_columns = {
        c["name"] for c in inspector.get_columns("workspaces")}
    assert {"wsid", "name", "description", "created_at"} <= workspace_columns

    project_columns = {c["name"] for c in inspector.get_columns("projects")}
    assert "wsid" in project_columns

    foreign_keys = inspector.get_foreign_keys("projects")
    assert any(
        fk["referred_table"] == "workspaces"
        and fk["constrained_columns"] == ["wsid"]
        for fk in foreign_keys
    )


# ---------- workspace CRUD ----------
def test_workspace_crud(client):
    created = create_workspace(client)
    wsid = created["wsid"]
    assert len(wsid) == 8
    assert created["name"] == "Engineering"
    assert created["description"] == "Team space"
    assert created["project_count"] == 0
    assert created["created_at"]

    listed = client.get("/workspaces")
    assert listed.status_code == 200
    assert [w["wsid"] for w in listed.json()] == [wsid]

    fetched = client.get(f"/workspaces/{wsid}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Engineering"

    updated = client.put(
        f"/workspaces/{wsid}",
        json={"name": "Platform", "description": "Renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Platform"
    assert updated.json()["description"] == "Renamed"

    deleted = client.delete(f"/workspaces/{wsid}")
    assert deleted.status_code == 204
    assert client.get(f"/workspaces/{wsid}").status_code == 404


def test_workspace_404s(client):
    assert client.get("/workspaces/nope").status_code == 404
    assert client.put(
        "/workspaces/nope", json={"name": "x"}).status_code == 404
    assert client.delete("/workspaces/nope").status_code == 404


def test_empty_workspace_name_rejected(client):
    assert client.post(
        "/workspaces", json={"name": "   "}).status_code == 400


# ---------- project ownership ----------
def test_create_project_inside_workspace(client):
    workspace = create_workspace(client)
    project = create_project(client, wsid=workspace["wsid"])

    assert project["wsid"] == workspace["wsid"]

    fetched = client.get(f"/projects/{project['prid']}").json()
    assert fetched["wsid"] == workspace["wsid"]
    assert fetched["report"]["event_count"] == 1

    listed = client.get(
        "/projects", params={"wsid": workspace["wsid"]}).json()
    assert [p["prid"] for p in listed] == [project["prid"]]


def test_create_project_in_unknown_workspace_rejected(client):
    response = client.post("/projects", json={
        "wsid": "missing1",
        "title": "Orphan",
        "events": [event()],
    })
    assert response.status_code == 404


def test_project_without_wsid_uses_default_workspace(client):
    first = create_project(client, title="First")
    second = create_project(client, title="Second")

    assert first["wsid"]
    assert first["wsid"] == second["wsid"]

    workspaces = client.get("/workspaces").json()
    assert len(workspaces) == 1
    assert workspaces[0]["wsid"] == first["wsid"]
    assert workspaces[0]["name"] == "My Workspace"
    assert workspaces[0]["project_count"] == 2


def test_list_projects_filtered_by_workspace(client):
    first_ws = create_workspace(client, name="First")
    second_ws = create_workspace(client, name="Second")
    first_project = create_project(
        client, wsid=first_ws["wsid"], title="One")
    second_project = create_project(
        client, wsid=second_ws["wsid"], title="Two")

    all_projects = client.get("/projects").json()
    assert {p["prid"] for p in all_projects} == {
        first_project["prid"], second_project["prid"]}

    only_first = client.get(
        "/projects", params={"wsid": first_ws["wsid"]}).json()
    assert [p["prid"] for p in only_first] == [first_project["prid"]]

    assert client.get(
        "/projects", params={"wsid": "missing1"}).status_code == 404


def test_delete_workspace_cascades_projects(client):
    workspace = create_workspace(client)
    first = create_project(client, wsid=workspace["wsid"], title="One")
    second = create_project(client, wsid=workspace["wsid"], title="Two")

    assert client.delete(
        f"/workspaces/{workspace['wsid']}").status_code == 204

    assert client.get(f"/projects/{first['prid']}").status_code == 404
    assert client.get(f"/projects/{second['prid']}").status_code == 404
    assert client.get("/projects").json() == []

    with SessionLocal() as session:
        assert session.query(ProjectModel).count() == 0


def test_delete_workspace_keeps_other_workspaces(client):
    first_ws = create_workspace(client, name="First")
    second_ws = create_workspace(client, name="Second")
    kept = create_project(client, wsid=second_ws["wsid"])

    client.delete(f"/workspaces/{first_ws['wsid']}")

    assert client.get(f"/workspaces/{second_ws['wsid']}").status_code == 200
    assert client.get(f"/projects/{kept['prid']}").status_code == 200


# ---------- store layer ----------
def test_store_workspace_roundtrip():
    from dag_scheduler import Event, Project, Workspace

    workspace = store.create_workspace(
        Workspace(wsid="ws000001", name="Store WS", description="d"))
    assert store.get_workspace("ws000001") == workspace
    assert [w.wsid for w in store.list_workspaces()] == ["ws000001"]

    start = ORIGIN
    project = Project(
        prid="pr000001",
        title="Stored",
        wsid=workspace.wsid,
        origin=start,
        events=[Event("T1", "A", 60, 1, start,
                      start + datetime.timedelta(hours=1), [])],
    )
    store.create_project(project)

    stored = store.get_project("pr000001")
    assert stored is not None
    assert stored.wsid == "ws000001"
    assert [p.prid for p in store.list_projects(wsid="ws000001")] == [
        "pr000001"]

    renamed = store.update_workspace(
        Workspace(wsid="ws000001", name="Renamed"))
    assert renamed is not None and renamed.name == "Renamed"

    assert store.delete_workspace("ws000001") is True
    assert store.get_project("pr000001") is None


# ---------- pre-workspace schema migration ----------
def test_existing_projects_table_gains_wsid(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from api.db import Base, _add_wsid_column

    legacy_engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with legacy_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE projects (
                prid VARCHAR PRIMARY KEY,
                title VARCHAR,
                description TEXT,
                origin VARCHAR,
                ddl VARCHAR,
                events_json TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            INSERT INTO projects
                (prid, title, description, origin, ddl, events_json,
                 created_at, updated_at)
            VALUES
                ('old1', 'Old Project', '', '2026-01-01T09:00:00+08:00',
                 NULL, '[]', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
        """))

        # The workspaces table is new; the old projects table must be kept.
        Base.metadata.create_all(bind=conn)
        _add_wsid_column(conn)

        row = conn.execute(text(
            "SELECT prid, wsid FROM projects")).mappings().one()
        assert row["prid"] == "old1"
        assert row["wsid"]

        workspaces = conn.execute(text(
            "SELECT COUNT(*) FROM workspaces")).scalar_one()
        assert workspaces == 1

        columns = {c["name"] for c in inspect(conn).get_columns("projects")}
        assert "wsid" in columns
    legacy_engine.dispose()


# ---------- move project between workspaces ----------
def test_move_project_between_workspaces(client):
    source = create_workspace(client, name="Source")
    target = create_workspace(client, name="Target")
    project = create_project(
        client, wsid=source["wsid"], title="Movable",
        events=[event("T1"), event("T2")])

    response = client.put(
        f"/projects/{project['prid']}",
        json={"wsid": target["wsid"]},
    )

    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["wsid"] == target["wsid"]
    assert len(moved["events"]) == 2
    assert moved["report"]["event_count"] == 2

    assert client.get(
        "/projects", params={"wsid": source["wsid"]}).json() == []
    target_projects = client.get(
        "/projects", params={"wsid": target["wsid"]}).json()
    assert [p["prid"] for p in target_projects] == [project["prid"]]
    assert client.get(
        f"/projects/{project['prid']}").json()["wsid"] == target["wsid"]

    # Workspace counts reflect the move.
    counts = {
        w["wsid"]: w["project_count"]
        for w in client.get("/workspaces").json()
    }
    assert counts[source["wsid"]] == 0
    assert counts[target["wsid"]] == 1


def test_move_project_to_unknown_workspace_rejected(client):
    source = create_workspace(client, name="Source")
    project = create_project(client, wsid=source["wsid"])

    response = client.put(
        f"/projects/{project['prid']}",
        json={"wsid": "missing1"},
    )
    assert response.status_code == 404

    fetched = client.get(f"/projects/{project['prid']}").json()
    assert fetched["wsid"] == source["wsid"]
