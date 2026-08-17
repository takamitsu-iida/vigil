import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import simple_incident.models  # noqa: F401 (テーブル登録のため)
from simple_incident.database import get_session
from simple_incident.main import app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    app.dependency_overrides.clear()


# ---- Users ----

def test_create_user(client: TestClient):
    res = client.post("/api/v1/users", json={"name": "Alice", "email": "alice@example.com"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Alice"
    assert "id" in data


def test_list_users(client: TestClient):
    client.post("/api/v1/users", json={"name": "Alice"})
    client.post("/api/v1/users", json={"name": "Bob"})
    res = client.get("/api/v1/users")
    assert res.status_code == 200
    assert len(res.json()) == 2


# ---- Schedules ----

def test_update_oncall_creates_schedule(client: TestClient):
    user = client.post("/api/v1/users", json={"name": "Alice"}).json()
    res = client.put("/api/v1/schedules/ops/oncall", json={"current_user_id": user["id"]})
    assert res.status_code == 200
    assert res.json()["current_user_id"] == user["id"]
    assert res.json()["team_name"] == "ops"


def test_update_oncall_switches_user(client: TestClient):
    alice = client.post("/api/v1/users", json={"name": "Alice"}).json()
    bob = client.post("/api/v1/users", json={"name": "Bob"}).json()
    client.put("/api/v1/schedules/ops/oncall", json={"current_user_id": alice["id"]})
    res = client.put("/api/v1/schedules/ops/oncall", json={"current_user_id": bob["id"]})
    assert res.json()["current_user_id"] == bob["id"]


# ---- Alerts ----

def test_receive_alert_no_schedule(client: TestClient):
    res = client.post(
        "/api/v1/alerts",
        json={"title": "CPU High", "description": "90%", "source": "Prometheus"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "triggered"
    assert data["assigned_user_id"] is None


def test_receive_alert_assigns_oncall_user(client: TestClient):
    user = client.post("/api/v1/users", json={"name": "Alice"}).json()
    client.put("/api/v1/schedules/default/oncall", json={"current_user_id": user["id"]})
    res = client.post("/api/v1/alerts", json={"title": "Disk Full", "team_name": "default"})
    assert res.status_code == 201
    assert res.json()["assigned_user_id"] == user["id"]


# ---- Incidents ----

def test_get_incident(client: TestClient):
    inc = client.post("/api/v1/alerts", json={"title": "CPU"}).json()
    res = client.get(f"/api/v1/incidents/{inc['id']}")
    assert res.status_code == 200
    assert res.json()["title"] == "CPU"


def test_get_incident_not_found(client: TestClient):
    res = client.get("/api/v1/incidents/nonexistent-id")
    assert res.status_code == 404


def test_list_incidents(client: TestClient):
    client.post("/api/v1/alerts", json={"title": "A"})
    client.post("/api/v1/alerts", json={"title": "B"})
    res = client.get("/api/v1/incidents")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_list_incidents_filter_by_status(client: TestClient):
    r1 = client.post("/api/v1/alerts", json={"title": "A"}).json()
    client.post("/api/v1/alerts", json={"title": "B"})
    client.post(f"/api/v1/incidents/{r1['id']}/acknowledge")

    triggered = client.get("/api/v1/incidents?status=triggered").json()
    acknowledged = client.get("/api/v1/incidents?status=acknowledged").json()
    assert len(triggered) == 1
    assert len(acknowledged) == 1


def test_list_incidents_pagination(client: TestClient):
    for i in range(5):
        client.post("/api/v1/alerts", json={"title": f"Alert {i}"})

    page1 = client.get("/api/v1/incidents?limit=2&offset=0").json()
    page2 = client.get("/api/v1/incidents?limit=2&offset=2").json()
    page3 = client.get("/api/v1/incidents?limit=2&offset=4").json()
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1


# ---- Acknowledge ----

def test_acknowledge_incident(client: TestClient):
    inc = client.post("/api/v1/alerts", json={"title": "A"}).json()
    res = client.post(f"/api/v1/incidents/{inc['id']}/acknowledge")
    assert res.status_code == 200
    assert res.json()["status"] == "acknowledged"


def test_acknowledge_not_found(client: TestClient):
    res = client.post("/api/v1/incidents/nonexistent-id/acknowledge")
    assert res.status_code == 404


# ---- Resolve ----

def test_resolve_incident(client: TestClient):
    inc = client.post("/api/v1/alerts", json={"title": "A"}).json()
    res = client.post(f"/api/v1/incidents/{inc['id']}/resolve")
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"


def test_resolve_not_found(client: TestClient):
    res = client.post("/api/v1/incidents/nonexistent-id/resolve")
    assert res.status_code == 404
