import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from api import app
from api import store


TZ = ZoneInfo("Asia/Shanghai")
ORIGIN = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=TZ)


def dt(minutes):
    return (ORIGIN + datetime.timedelta(minutes=minutes)).isoformat()


@pytest.fixture(autouse=True)
def clear_store():
    """Clear in-memory store between tests."""
    store._sessions.clear()
    yield
    store._sessions.clear()


@pytest.fixture
def client():
    return TestClient(app)


def plan_payload():
    return {
        "version": 1,
        "origin": ORIGIN.isoformat(),
        "events": [
            {"eid": "A", "description": "Design", "duration": 30,
             "priority": 1, "start": dt(0), "deadline": dt(45),
             "dependencies": []},
            {"eid": "B", "description": "Impl", "duration": 15,
             "priority": 2, "start": dt(0), "deadline": dt(45),
             "dependencies": ["A"]},
        ],
    }


# ---------- create ----------
def test_create_plan(client):
    r = client.post("/plan", json=plan_payload())
    assert r.status_code == 200
    body = r.json()
    assert "plan_id" in body
    assert body["cpm"]["makespan"] == 45
    assert body["cpm"]["critical_path"] == ["A", "B"]


def test_create_plan_bad_payload(client):
    r = client.post("/plan", json={"version": 1, "origin": "bad",
                                   "events": []})
    assert r.status_code == 400


def test_create_plan_business_error(client):
    payload = plan_payload()
    payload["events"][0]["start"] = dt(-10)   # before origin
    r = client.post("/plan", json=payload)
    assert r.status_code == 400


# ---------- get ----------
def test_get_plan_roundtrip(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert len(data["events"]) == 2


def test_get_plan_404(client):
    r = client.get("/plan/nonexistent")
    assert r.status_code == 404


# ---------- gantt / report ----------
def test_gantt(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/gantt")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert all("status" in row for row in rows)


def test_report(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/report")
    assert r.status_code == 200
    body = r.json()
    assert body["is_feasible"] is True
    assert body["overdue_count"] == 0


# ---------- schedule ----------
def test_schedule_workers_1(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/schedule", params={"workers": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["makespan"] == 45
    assert body["workers"] == 1


def test_schedule_bad_workers(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/schedule", params={"workers": 0})
    assert r.status_code == 400


# ---------- graph ----------
def test_graph_mermaid(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/graph", params={"format": "mermaid"})
    assert r.status_code == 200
    assert r.json()["format"] == "mermaid"
    assert "flowchart" in r.json()["content"]


def test_graph_dot(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/graph", params={"format": "dot"})
    assert r.status_code == 200
    assert "digraph" in r.json()["content"]


def test_graph_bad_format(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.get(f"/plan/{pid}/graph", params={"format": "svg"})
    assert r.status_code == 400


# ---------- list / delete ----------
def test_list_plans(client):
    client.post("/plan", json=plan_payload())
    client.post("/plan", json=plan_payload())
    r = client.get("/plans")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_delete_plan(client):
    pid = client.post("/plan", json=plan_payload()).json()["plan_id"]
    r = client.delete(f"/plan/{pid}")
    assert r.status_code == 204
    assert client.get(f"/plan/{pid}").status_code == 404


def test_delete_missing(client):
    r = client.delete("/plan/nonexistent")
    assert r.status_code == 404


def test_error_format_404(client):
    r = client.get("/plan/nonexistent")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["status"] == 404


def test_error_format_400(client):
    r = client.post("/plan", json={"version": 1,
                    "origin": "bad", "events": []})
    assert r.status_code == 400
    body = r.json()
    assert "error" in body
    assert body["error"]["status"] == 400


def test_cors_headers(client):
    r = client.options(
        "/plan",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "*"
