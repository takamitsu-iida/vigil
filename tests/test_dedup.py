import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import vigil.models  # noqa: F401
from vigil.crud import compute_fingerprint
from vigil.database import get_session
from vigil.main import app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---- compute_fingerprint ----

def test_fingerprint_same_input_gives_same_hash():
    assert compute_fingerprint("prometheus", "CPU High") == compute_fingerprint("prometheus", "CPU High")


def test_fingerprint_case_insensitive():
    assert compute_fingerprint("Prometheus", "CPU High") == compute_fingerprint("prometheus", "cpu high")


def test_fingerprint_different_source_gives_different_hash():
    assert compute_fingerprint("prometheus", "CPU High") != compute_fingerprint("grafana", "CPU High")


def test_fingerprint_different_title_gives_different_hash():
    assert compute_fingerprint("prometheus", "CPU High") != compute_fingerprint("prometheus", "Disk Full")


# ---- deduplication via API ----

def test_duplicate_alert_returns_existing_incident(client: TestClient):
    body = {"title": "CPU High", "source": "prometheus"}
    r1 = client.post("/api/v1/alerts", json=body)
    assert r1.status_code == 201
    id1 = r1.json()["id"]

    r2 = client.post("/api/v1/alerts", json=body)
    assert r2.status_code == 200
    assert r2.json()["id"] == id1


def test_duplicate_alert_updates_updated_at(client: TestClient):
    body = {"title": "CPU High", "source": "prometheus"}
    r1 = client.post("/api/v1/alerts", json=body)
    r2 = client.post("/api/v1/alerts", json=body)
    assert r2.json()["updated_at"] >= r1.json()["updated_at"]


def test_different_title_creates_new_incident(client: TestClient):
    r1 = client.post("/api/v1/alerts", json={"title": "CPU High", "source": "prometheus"})
    r2 = client.post("/api/v1/alerts", json={"title": "Disk Full", "source": "prometheus"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_different_source_creates_new_incident(client: TestClient):
    r1 = client.post("/api/v1/alerts", json={"title": "CPU High", "source": "prometheus"})
    r2 = client.post("/api/v1/alerts", json={"title": "CPU High", "source": "grafana"})
    assert r1.json()["id"] != r2.json()["id"]


def test_resolved_incident_allows_new_incident(client: TestClient):
    body = {"title": "CPU High", "source": "prometheus"}
    r1 = client.post("/api/v1/alerts", json=body)
    client.post(f"/api/v1/incidents/{r1.json()['id']}/resolve")

    r2 = client.post("/api/v1/alerts", json=body)
    assert r2.status_code == 201
    assert r2.json()["id"] != r1.json()["id"]


def test_acknowledged_incident_deduplicates(client: TestClient):
    body = {"title": "CPU High", "source": "prometheus"}
    r1 = client.post("/api/v1/alerts", json=body)
    client.post(f"/api/v1/incidents/{r1.json()['id']}/acknowledge")

    r2 = client.post("/api/v1/alerts", json=body)
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]
