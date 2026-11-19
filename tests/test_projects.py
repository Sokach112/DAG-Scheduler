"""Tests for persistent project CRUD and project-scoped scheduling."""

import datetime

import pytest
from fastapi.testclient import TestClient

from api import app, store
from api.db import ProjectModel, SessionLocal, engine


TZ = datetime.timezone(datetime.timedelta(hours=8))
ORIGIN = datetime.datetime(2026, 11, 19, 9, 0, tzinfo=TZ)


def iso(minutes: int = 0) -> str:
    return (ORIGIN + datetime.timedelta(minutes=minutes)).isoformat()


def event(eid="A", description="Task", duration=60, priority=1,
          start=0, deadline=180, dependencies=None):
    return {
        "eid": eid,
        "description": description,
        "details": "",
        "duration": duration,
        "priority": priority,
        "start": iso(start),
        "deadline": iso(deadline),
        "dependencies": dependencies or [],
    }


@pytest.fixture(autouse=True)
def clear_projects():
    store._sessions.clear()
    with SessionLocal() as session:
        session.query(ProjectModel).delete()
        session.commit()
    yield
    with SessionLocal() as session:
        session.query(ProjectModel).delete()
        session.commit()


@pytest.fixture
def client():
    return TestClient(app)


def create_project(client, **overrides):
    payload = {
        "title": "Alpha",
        "description": "First project",
        "events": [
            event("A", duration=60),
            event("B", duration=30, dependencies=["A"]),
        ],
    }
    payload.update(overrides)
    response = client.post("/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- create / read / list ----------
def test_create_project_auto_origin_and_report(client):
    body = create_project(client)

    assert body["prid"]
    assert body["title"] == "Alpha"
    assert body["description"] == "First project"
    assert body["origin"] == iso(0)
    assert body["ddl"] is None
    assert len(body["events"]) == 2
    report = body["report"]
    assert report["event_count"] == 2
    assert report["makespan"] == 90
    assert report["makespan_human"] == "1h 30m"
    assert report["max_concurrency"] == 1


def test_get_project_roundtrip(client):
    created = create_project(client)

    response = client.get(f"/projects/{created['prid']}")

    assert response.status_code == 200
    body = response.json()
    assert body["prid"] == created["prid"]
    assert [e["eid"] for e in body["events"]] == ["A", "B"]
    assert body["events"][1]["dependencies"] == ["A"]
    assert body["report"]["makespan"] == 90


def test_list_projects(client):
    first = create_project(client, title="First")
    second = create_project(client, title="Second")

    response = client.get("/projects")

    assert response.status_code == 200
    body = response.json()
    assert {p["prid"] for p in body} == {first["prid"], second["prid"]}
    assert all("event_count" in p and "makespan" in p for p in body)


def test_project_survives_engine_restart(client):
    created = create_project(client)

    engine.dispose()

    response = client.get(f"/projects/{created['prid']}")
    assert response.status_code == 200
    assert response.json()["report"]["makespan"] == 90


def test_empty_project(client):
    response = client.post("/projects", json={"title": "Empty"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["events"] == []
    assert body["report"]["event_count"] == 0
    assert body["report"]["makespan"] == 0
    assert body["report"]["max_concurrency"] == 0
    assert body["origin"]


def test_ddl_is_persisted(client):
    created = create_project(client, ddl=iso(600))
    assert created["ddl"] == iso(600)

    body = client.get(f"/projects/{created['prid']}").json()
    assert body["ddl"] == iso(600)


# ---------- update ----------
def test_update_metadata_only_keeps_events(client):
    created = create_project(client)

    response = client.put(
        f"/projects/{created['prid']}",
        json={"title": "Renamed", "description": "Updated"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["description"] == "Updated"
    assert len(body["events"]) == 2
    assert body["report"]["makespan"] == 90


def test_update_events(client):
    created = create_project(client)

    response = client.put(
        f"/projects/{created['prid']}",
        json={"events": [event("A", duration=120)]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["events"]) == 1
    assert body["report"]["makespan"] == 120


def test_update_rebases_origin_when_events_move_earlier(client):
    created = create_project(client)
    assert created["origin"] == iso(0)

    response = client.put(
        f"/projects/{created['prid']}",
        json={"events": [event("A", start=-60)]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["origin"] == iso(-60)


def test_update_explicit_origin_before_events(client):
    created = create_project(client)

    response = client.put(
        f"/projects/{created['prid']}",
        json={"origin": iso(60)},
    )

    assert response.status_code == 400


def test_update_empty_events(client):
    created = create_project(client)

    response = client.put(
        f"/projects/{created['prid']}",
        json={"events": []},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["events"] == []
    assert body["report"]["makespan"] == 0


def test_ddl_before_origin_rejected(client):
    response = client.post(
        "/projects",
        json={"title": "Bad", "ddl": iso(-60), "events": [event("A")]},
    )
    assert response.status_code == 400


# ---------- validation ----------
def test_cycle_rejected(client):
    response = client.post("/projects", json={
        "title": "Cycle",
        "events": [
            event("A", dependencies=["B"]),
            event("B", dependencies=["A"]),
        ],
    })
    assert response.status_code == 400


def test_duplicate_eid_rejected(client):
    response = client.post("/projects", json={
        "title": "Dup",
        "events": [event("A"), event("A")],
    })
    assert response.status_code == 400


def test_unknown_dependency_rejected(client):
    response = client.post("/projects", json={
        "title": "Bad dep",
        "events": [event("A", dependencies=["GHOST"])],
    })
    assert response.status_code == 400


def test_naive_datetime_rejected(client):
    bad = event("A")
    bad["start"] = "2026-11-19T09:00:00"
    response = client.post(
        "/projects", json={"title": "Naive", "events": [bad]})
    assert response.status_code == 400


# ---------- delete ----------
def test_delete_project(client):
    created = create_project(client)

    assert client.delete(f"/projects/{created['prid']}").status_code == 204
    assert client.get(f"/projects/{created['prid']}").status_code == 404
    assert client.delete(f"/projects/{created['prid']}").status_code == 404
    assert client.get("/projects").json() == []


def test_missing_project_404(client):
    assert client.get("/projects/nope").status_code == 404
    assert client.put("/projects/nope", json={"title": "x"}).status_code == 404
    assert client.delete("/projects/nope").status_code == 404


# ---------- project-scoped scheduling ----------
def test_project_scoped_endpoints(client):
    created = create_project(client)
    prid = created["prid"]

    report = client.get(f"/projects/{prid}/report")
    assert report.status_code == 200
    assert report.json()["makespan"] == 90

    gantt = client.get(f"/projects/{prid}/gantt")
    assert gantt.status_code == 200
    assert len(gantt.json()) == 2

    schedule = client.get(
        f"/projects/{prid}/schedule", params={"workers": 1})
    assert schedule.status_code == 200
    body = schedule.json()
    assert body["workers"] == 1
    assert body["makespan"] == 90
    assert body["tasks"]["A"]["description"] == "Task"

    graph = client.get(
        f"/projects/{prid}/graph", params={"format": "mermaid"})
    assert graph.status_code == 200
    assert "flowchart" in graph.json()["content"]

    bad_workers = client.get(
        f"/projects/{prid}/schedule", params={"workers": 0})
    assert bad_workers.status_code == 400

    bad_format = client.get(
        f"/projects/{prid}/graph", params={"format": "svg"})
    assert bad_format.status_code == 400


# ---------- legacy database migration ----------
def test_legacy_integer_prid_schema_is_migrated(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from api.db import _migrate_legacy_projects

    legacy_engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with legacy_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE projects (
                prid INTEGER PRIMARY KEY,
                title VARCHAR,
                description VARCHAR,
                origin VARCHAR,
                ddl VARCHAR,
                events_json TEXT,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            INSERT INTO projects
                (prid, title, description, origin, ddl, events_json, updated_at)
            VALUES
                (1, 'Legacy', 'old', '2026-01-01T09:00:00+08:00',
                 NULL, '[]', '2026-01-01 00:00:00')
        """))

        _migrate_legacy_projects(conn)

        row = conn.execute(text(
            "SELECT prid, title, description, origin FROM projects"
        )).mappings().one()
        assert row["prid"] == "p1"
        assert row["title"] == "Legacy"
        assert row["origin"] == "2026-01-01T09:00:00+08:00"

        columns = {c["name"] for c in inspect(conn).get_columns("projects")}
        assert {"created_at", "updated_at", "events_json"} <= columns
    legacy_engine.dispose()
