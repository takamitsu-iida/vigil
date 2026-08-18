import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from unittest.mock import AsyncMock, patch

import vigil.models  # noqa: F401
from vigil.database import get_session
from vigil.main import app
from vigil import crud
from vigil.models import IncidentStatus


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


@pytest.fixture(name="mem_session")
def mem_session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session, engine


# ---- Policy CRUD API ----

def test_create_policy(client: TestClient):
    res = client.post("/api/v1/policies", json={"name": "Ops Policy", "team_name": "ops"})
    assert res.status_code == 201
    assert res.json()["team_name"] == "ops"


def test_get_policy(client: TestClient):
    client.post("/api/v1/policies", json={"name": "Ops Policy", "team_name": "ops"})
    res = client.get("/api/v1/policies/ops")
    assert res.status_code == 200
    assert res.json()["name"] == "Ops Policy"


def test_get_policy_not_found(client: TestClient):
    res = client.get("/api/v1/policies/nonexistent")
    assert res.status_code == 404


def test_add_step(client: TestClient):
    user = client.post("/api/v1/users", json={"name": "Alice"}).json()
    policy = client.post("/api/v1/policies", json={"name": "P", "team_name": "ops"}).json()
    res = client.post(f"/api/v1/policies/{policy['id']}/steps",
                      json={"user_id": user["id"], "timeout_minutes": 5})
    assert res.status_code == 201
    assert res.json()["step_order"] == 1
    assert res.json()["timeout_minutes"] == 5


def test_steps_auto_order(client: TestClient):
    alice = client.post("/api/v1/users", json={"name": "Alice"}).json()
    bob = client.post("/api/v1/users", json={"name": "Bob"}).json()
    policy = client.post("/api/v1/policies", json={"name": "P", "team_name": "ops"}).json()
    s1 = client.post(f"/api/v1/policies/{policy['id']}/steps",
                     json={"user_id": alice["id"], "timeout_minutes": 5}).json()
    s2 = client.post(f"/api/v1/policies/{policy['id']}/steps",
                     json={"user_id": bob["id"], "timeout_minutes": 10}).json()
    assert s1["step_order"] == 1
    assert s2["step_order"] == 2


def test_list_steps(client: TestClient):
    alice = client.post("/api/v1/users", json={"name": "Alice"}).json()
    policy = client.post("/api/v1/policies", json={"name": "P", "team_name": "ops"}).json()
    client.post(f"/api/v1/policies/{policy['id']}/steps",
                json={"user_id": alice["id"], "timeout_minutes": 5})
    res = client.get(f"/api/v1/policies/{policy['id']}/steps")
    assert res.status_code == 200
    assert len(res.json()) == 1


# ---- Alert uses policy first step timeout ----

def test_alert_uses_policy_first_step_timeout(client: TestClient):
    """ポリシーが設定されているチームへのアラートはポリシーと紐づく"""
    alice = client.post("/api/v1/users", json={"name": "Alice"}).json()
    client.put("/api/v1/schedules/ops/oncall", json={"current_user_id": alice["id"]})
    policy = client.post("/api/v1/policies", json={"name": "Ops Policy", "team_name": "ops"}).json()
    client.post(f"/api/v1/policies/{policy['id']}/steps",
                json={"user_id": alice["id"], "timeout_minutes": 3})

    res = client.post("/api/v1/alerts", json={"title": "CPU High", "team_name": "ops"})
    assert res.status_code == 201
    assert res.json()["policy_id"] == policy["id"]


# ---- _escalate multi-step logic ----

async def test_escalate_notifies_step_user(mem_session):
    session, engine = mem_session
    alice = crud.create_user(session, name="Alice")
    bob = crud.create_user(session, name="Bob")
    policy = crud.create_policy(session, name="P", team_name="ops")
    crud.add_step(session, policy_id=policy.id, user_id=alice.id, timeout_minutes=5)
    crud.add_step(session, policy_id=policy.id, user_id=bob.id, timeout_minutes=10)
    incident = crud.create_incident(session, title="CPU High", policy_id=policy.id)

    from vigil.services import escalation
    mock_send = AsyncMock()
    with (
        patch("vigil.services.notifier.send_alert", mock_send),
        patch("vigil.database.engine", engine),
        patch.object(escalation, "schedule_escalation"),  # 再スケジュールはモック
    ):
        await escalation._escalate(incident.id)

    mock_send.assert_awaited_once()
    _, called_user = mock_send.call_args.args
    assert called_user.id == alice.id  # step 1 = Alice


async def test_escalate_advances_to_next_step(mem_session):
    session, engine = mem_session
    alice = crud.create_user(session, name="Alice")
    bob = crud.create_user(session, name="Bob")
    policy = crud.create_policy(session, name="P", team_name="ops")
    crud.add_step(session, policy_id=policy.id, user_id=alice.id, timeout_minutes=5)
    crud.add_step(session, policy_id=policy.id, user_id=bob.id, timeout_minutes=10)
    incident = crud.create_incident(session, title="CPU High", policy_id=policy.id)

    from vigil.services import escalation
    with (
        patch("vigil.services.notifier.send_alert", AsyncMock()),
        patch("vigil.database.engine", engine),
        patch.object(escalation, "schedule_escalation"),
    ):
        await escalation._escalate(incident.id)  # step 0 → Alice, advance to step 1

    session.refresh(incident)
    assert incident.escalation_step == 1  # 次回は Bob に通知される


async def test_escalate_stays_on_last_step(mem_session):
    """最終ステップ以降はそのステップのユーザーに通知し続ける"""
    session, engine = mem_session
    alice = crud.create_user(session, name="Alice")
    bob = crud.create_user(session, name="Bob")
    policy = crud.create_policy(session, name="P", team_name="ops")
    crud.add_step(session, policy_id=policy.id, user_id=alice.id, timeout_minutes=5)
    crud.add_step(session, policy_id=policy.id, user_id=bob.id, timeout_minutes=10)
    incident = crud.create_incident(session, title="CPU High", policy_id=policy.id)
    incident.escalation_step = 1  # すでに最終ステップ
    session.add(incident)
    session.commit()

    mock_send = AsyncMock()
    from vigil.services import escalation
    with (
        patch("vigil.services.notifier.send_alert", mock_send),
        patch("vigil.database.engine", engine),
        patch.object(escalation, "schedule_escalation"),
    ):
        await escalation._escalate(incident.id)

    _, called_user = mock_send.call_args.args
    assert called_user.id == bob.id  # 最終ステップ = Bob
