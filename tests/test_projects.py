"""Tests for persistent project CRUD and project-scoped scheduling."""

import datetime

import pytest
from fastapi.testclient import TestClient

from api import app, store
from api.db import ProjectModel, SessionLocal, WorkspaceModel, engine


TZ = datetime.timezone(datetime.timedelta(hours=8))
ORIGIN = datetime.datetime(2026, 11, 19, 9, 0, tzinfo=TZ)


def iso(minutes: int = 0) -> str:
    return (ORIGIN + datetime.timedelta(minutes=minutes)).isoformat()


def event(eid="A", description="Task", duration=60, priority=1,
          start=0, deadline=180, dependencies=None, capable_workers=None,
          capable_workers_generic=None):
    return {
        "eid": eid,
        "description": description,
        "details": "",
        "duration": duration,
        "priority": priority,
        "start": iso(start),
        "deadline": iso(deadline),
        "dependencies": dependencies or [],
        "capable_workers": capable_workers or [],
        "capable_workers_generic": capable_workers_generic or [],
    }


@pytest.fixture(autouse=True)
def clear_projects():
    store._sessions.clear()

    def clear_tables():
        with SessionLocal() as session:
            session.query(ProjectModel).delete()
            session.query(WorkspaceModel).delete()
            session.commit()

    clear_tables()
    yield
    clear_tables()


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
        conn.execute(text(
            "CREATE INDEX ix_projects_prid ON projects (prid)"))
        conn.execute(text(
            "CREATE INDEX ix_projects_title ON projects (title)"))
        conn.execute(text("""
            INSERT INTO projects
                (prid, title, description, origin, ddl, events_json, updated_at)
            VALUES
                (1, 'Legacy', 'old', '2026-01-01T09:00:00+08:00',
                 NULL, '[]', '2026-01-01 00:00:00')
        """))

        _migrate_legacy_projects(conn)

        row = conn.execute(text(
            "SELECT prid, wsid, title, description, origin FROM projects"
        )).mappings().one()
        assert row["prid"] == "p1"
        assert row["wsid"]
        assert row["title"] == "Legacy"
        assert row["origin"] == "2026-01-01T09:00:00+08:00"
        assert conn.execute(text(
            "SELECT COUNT(*) FROM workspaces")).scalar_one() == 1

        columns = {c["name"] for c in inspect(conn).get_columns("projects")}
        assert {"created_at", "updated_at", "events_json"} <= columns

        indexes = {i["name"] for i in inspect(conn).get_indexes("projects")}
        assert {"ix_projects_prid", "ix_projects_title"} <= indexes
    legacy_engine.dispose()


# ---------- named workers / capabilities ----------
def test_worker_settings_roundtrip_and_defaults(client):
    default = create_project(client)
    assert default["worker_mode"] == "infinite"
    assert default["worker_count"] == 2
    assert default["single_worker_id"] is None
    assert default["active_worker_ids"] == []

    created = create_project(
        client,
        title="Team mode",
        workers=[
            {"wid": "alice", "name": "Alice"},
            {"wid": "bob", "name": "Bob"},
        ],
        worker_mode="team",
        worker_count=3,
        single_worker_id="alice",
        active_worker_ids=["alice", "bob"],
        events=[event("A")],
    )
    assert created["worker_mode"] == "team"
    assert created["worker_count"] == 3
    assert created["single_worker_id"] == "alice"
    assert created["active_worker_ids"] == ["alice", "bob"]

    fetched = client.get(f"/projects/{created['prid']}").json()
    assert fetched["worker_mode"] == "team"
    assert fetched["active_worker_ids"] == ["alice", "bob"]

    updated = client.put(
        f"/projects/{created['prid']}",
        json={"worker_mode": "1", "single_worker_id": "bob"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["worker_mode"] == "1"
    assert body["single_worker_id"] == "bob"
    assert body["active_worker_ids"] == ["alice", "bob"]
    assert body["worker_count"] == 3


def test_invalid_worker_settings_rejected(client):
    created = create_project(client, events=[event("A")])

    bad_mode = client.put(
        f"/projects/{created['prid']}",
        json={"worker_mode": "matrix"},
    )
    assert bad_mode.status_code == 400

    bad_count = client.put(
        f"/projects/{created['prid']}",
        json={"worker_count": 0},
    )
    assert bad_count.status_code == 400

    duplicate = client.put(
        f"/projects/{created['prid']}",
        json={"active_worker_ids": ["alice", "alice"]},
    )
    assert duplicate.status_code == 400


def test_team_and_generic_capabilities_are_independent(client):
    created = create_project(
        client,
        title="Dual capabilities",
        workers=[
            {"wid": "alice", "name": "Alice"},
            {"wid": "bob", "name": "Bob"},
        ],
        worker_mode="team",
        events=[event(
            "A",
            capable_workers=["alice"],
            capable_workers_generic=[1],
        )],
    )

    team = client.get(
        f"/projects/{created['prid']}/schedule"
        "?workers=2&worker_ids=alice,bob")
    assert team.status_code == 200, team.text
    assert team.json()["assignments"] == {"A": "alice"}

    generic = client.get(
        f"/projects/{created['prid']}/schedule?workers=2")
    assert generic.status_code == 200, generic.text
    assert generic.json()["assignments"] == {"A": 1}
    assert generic.json()["capability_fallbacks"] == []


def test_generic_capability_fallback(client):
    created = create_project(
        client,
        title="Generic fallback",
        events=[event("A", capable_workers_generic=[2])],
    )
    response = client.get(
        f"/projects/{created['prid']}/schedule?workers=2")
    assert response.status_code == 200
    body = response.json()
    assert body["assignments"]["A"] in {0, 1}
    assert body["capability_fallbacks"] == ["A"]


def test_list_projects_includes_workers(client):
    created = create_project(
        client,
        workers=[{"wid": "alice", "name": "Alice"}],
        events=[event("A")],
    )
    response = client.get("/projects")
    assert response.status_code == 200
    project = next(p for p in response.json() if p["prid"] == created["prid"])
    assert project["workers"] == [{"wid": "alice", "name": "Alice"}]


def test_project_workers_and_capabilities_roundtrip(client):
    body = create_project(
        client,
        title="Team",
        workers=[
            {"wid": "alice", "name": "Alice"},
            {"wid": "bob", "name": "Bob"},
        ],
        events=[event("A", duration=60, capable_workers=["alice"])],
    )

    assert body["workers"] == [
        {"wid": "alice", "name": "Alice"},
        {"wid": "bob", "name": "Bob"},
    ]
    assert body["events"][0]["capable_workers"] == ["alice"]

    fetched = client.get(f"/projects/{body['prid']}").json()
    assert fetched["workers"] == body["workers"]
    assert fetched["events"][0]["capable_workers"] == ["alice"]


def test_schedule_uses_active_named_workers(client):
    created = create_project(
        client,
        title="Team",
        workers=[
            {"wid": "alice", "name": "Alice"},
            {"wid": "bob", "name": "Bob"},
        ],
        events=[
            event("A", duration=60, capable_workers=["alice"]),
            event("B", duration=30, capable_workers=["bob"]),
        ],
    )

    response = client.get(
        f"/projects/{created['prid']}/schedule"
        "?workers=2&worker_ids=alice,bob")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workers"] == 2
    assert body["worker_ids"] == ["alice", "bob"]
    assert body["assignments"] == {"A": "alice", "B": "bob"}
    assert body["capability_fallbacks"] == []


def test_schedule_falls_back_when_no_capable_active_worker(client):
    created = create_project(
        client,
        title="Team",
        workers=[
            {"wid": "alice", "name": "Alice"},
            {"wid": "bob", "name": "Bob"},
        ],
        events=[event("A", duration=60, capable_workers=["alice"])],
    )

    response = client.get(
        f"/projects/{created['prid']}/schedule"
        "?workers=1&worker_ids=bob")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assignments"] == {"A": "bob"}
    assert body["capability_fallbacks"] == ["A"]


def test_schedule_without_ids_uses_generic_workers(client):
    created = create_project(
        client,
        title="Team",
        workers=[
            {"wid": "alice", "name": "Alice"},
            {"wid": "bob", "name": "Bob"},
        ],
        events=[event("A", duration=60)],
    )

    response = client.get(f"/projects/{created['prid']}/schedule?workers=2")
    assert response.status_code == 200, response.text
    assert response.json()["worker_ids"] == [0, 1]


def test_schedule_rejects_unknown_named_worker(client):
    created = create_project(
        client,
        title="Team",
        workers=[{"wid": "alice", "name": "Alice"}],
        events=[event("A", duration=60)],
    )

    response = client.get(
        f"/projects/{created['prid']}/schedule?worker_ids=ghost")
    assert response.status_code == 400
    assert "unknown worker" in response.json()["error"]["detail"]


def test_schedule_rejects_invalid_worker_count(client):
    created = create_project(
        client,
        workers=[{"wid": "alice", "name": "Alice"}],
        events=[event("A")],
    )
    response = client.get(
        f"/projects/{created['prid']}/schedule?workers=0")
    assert response.status_code == 400
    assert "workers must be" in response.json()["error"]["detail"]


def test_schedule_rejects_worker_ids_without_roster(client):
    created = create_project(client, events=[event("A")])

    response = client.get(
        f"/projects/{created['prid']}/schedule?worker_ids=alice")
    assert response.status_code == 400
    assert "no named workers" in response.json()["error"]["detail"]


def test_update_project_workers(client):
    created = create_project(
        client,
        workers=[{"wid": "alice", "name": "Alice"}],
        events=[event("A", capable_workers=["alice"])],
    )

    response = client.put(
        f"/projects/{created['prid']}",
        json={"workers": [
            {"wid": "alice", "name": "Alice A."},
            {"wid": "carol", "name": "Carol"},
        ]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [w["name"] for w in body["workers"]] == ["Alice A.", "Carol"]
    assert body["events"][0]["capable_workers"] == ["alice"]

    no_capable = client.get(
        f"/projects/{created['prid']}/schedule?worker_ids=carol")
    assert no_capable.status_code == 200
    assert no_capable.json()["capability_fallbacks"] == ["A"]
    assert no_capable.json()["assignments"] == {"A": "carol"}


def test_project_deadline_overdue_evaluation(client):
    created = create_project(
        client,
        ddl=iso(60),
        events=[event("A", duration=120, deadline=180)],
    )
    report = created["report"]
    assert report["overdue_count"] == 1
    assert report["project_overdue"] is True
    assert report["project_late_minutes"] == 60
    assert report["project_late_human"] == "1h"
    assert report["is_feasible"] is False

    gantt = client.get(f"/projects/{created['prid']}/gantt").json()
    assert gantt[0]["status"] == "overdue"

    schedule = client.get(
        f"/projects/{created['prid']}/schedule?workers=1").json()
    assert schedule["project_overdue"] is True
    assert schedule["project_late_minutes"] == 60
    assert schedule["tasks"]["A"]["status"] == "overdue"


def test_project_deadline_not_set_keeps_task_deadline_result(client):
    created = create_project(
        client,
        events=[event("A", duration=120, deadline=180)],
    )
    assert created["report"]["project_overdue"] is False
    assert created["report"]["project_ddl"] is None
