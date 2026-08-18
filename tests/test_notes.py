import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import vigil.models  # noqa: F401
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


@pytest.fixture(name="incident_id")
def incident_id_fixture(client: TestClient) -> str:
    res = client.post("/api/v1/alerts", json={"title": "CPU High", "source": "prometheus"})
    return res.json()["id"]


# ---- API ----

def test_add_note(client: TestClient, incident_id: str):
    res = client.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": "調査中"})
    assert res.status_code == 201
    assert res.json()["body"] == "調査中"
    assert res.json()["incident_id"] == incident_id


def test_add_note_with_author(client: TestClient, incident_id: str):
    user = client.post("/api/v1/users", json={"name": "Alice"}).json()
    res = client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        json={"body": "担当引き受けます", "author_user_id": user["id"]},
    )
    assert res.status_code == 201
    assert res.json()["author_user_id"] == user["id"]


def test_list_notes_empty(client: TestClient, incident_id: str):
    res = client.get(f"/api/v1/incidents/{incident_id}/notes")
    assert res.status_code == 200
    assert res.json() == []


def test_list_notes_ordered(client: TestClient, incident_id: str):
    client.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": "1件目"})
    client.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": "2件目"})
    res = client.get(f"/api/v1/incidents/{incident_id}/notes")
    notes = res.json()
    assert len(notes) == 2
    assert notes[0]["body"] == "1件目"
    assert notes[1]["body"] == "2件目"


def test_add_note_incident_not_found(client: TestClient):
    res = client.post("/api/v1/incidents/nonexistent/notes", json={"body": "test"})
    assert res.status_code == 404


def test_list_notes_incident_not_found(client: TestClient):
    res = client.get("/api/v1/incidents/nonexistent/notes")
    assert res.status_code == 404


# ---- Web UI ----

def test_incident_detail_shows_notes(client: TestClient, incident_id: str):
    client.post(f"/api/v1/incidents/{incident_id}/notes", json={"body": "対応開始"})
    res = client.get(f"/incidents/{incident_id}")
    assert res.status_code == 200
    assert "対応開始" in res.text
    assert "タイムライン" in res.text


def test_web_post_note_redirects(client: TestClient, incident_id: str):
    res = client.post(
        f"/incidents/{incident_id}/notes",
        data={"body": "Web から投稿"},
        follow_redirects=False,
    )
    assert res.status_code == 200
    assert res.headers.get("hx-redirect") == f"/incidents/{incident_id}"


def test_web_note_appears_after_post(client: TestClient, incident_id: str):
    client.post(f"/incidents/{incident_id}/notes", data={"body": "対応完了"})
    res = client.get(f"/incidents/{incident_id}")
    assert "対応完了" in res.text
