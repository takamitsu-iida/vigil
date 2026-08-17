import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import simple_incident.models  # noqa: F401 (テーブル登録のため)
from simple_incident import crud
from simple_incident.models import IncidentStatus


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------- User ----------

def test_create_and_get_user(session: Session):
    user = crud.create_user(session, name="Alice", slack_user_id="U001", email="alice@example.com")
    assert user.id is not None
    fetched = crud.get_user(session, user.id)
    assert fetched is not None
    assert fetched.name == "Alice"


def test_list_users(session: Session):
    crud.create_user(session, name="Alice")
    crud.create_user(session, name="Bob")
    users = crud.list_users(session)
    assert len(users) == 2


def test_get_user_not_found(session: Session):
    assert crud.get_user(session, "nonexistent-id") is None


# ---------- Schedule ----------

def test_get_schedule_by_team(session: Session):
    user = crud.create_user(session, name="Alice")
    from simple_incident.models import Schedule
    schedule = Schedule(team_name="ops", current_user_id=user.id)
    session.add(schedule)
    session.commit()

    result = crud.get_schedule_by_team(session, "ops")
    assert result is not None
    assert result.current_user_id == user.id


def test_update_oncall_user(session: Session):
    alice = crud.create_user(session, name="Alice")
    bob = crud.create_user(session, name="Bob")
    from simple_incident.models import Schedule
    session.add(Schedule(team_name="ops", current_user_id=alice.id))
    session.commit()

    updated = crud.update_oncall_user(session, "ops", bob.id)
    assert updated is not None
    assert updated.current_user_id == bob.id


def test_update_oncall_user_team_not_found(session: Session):
    user = crud.create_user(session, name="Alice")
    result = crud.update_oncall_user(session, "unknown-team", user.id)
    assert result is None


# ---------- Incident ----------

def test_create_and_get_incident(session: Session):
    user = crud.create_user(session, name="Alice")
    incident = crud.create_incident(
        session, title="CPU High", description="Server A", assigned_user_id=user.id
    )
    assert incident.id is not None
    assert incident.status == IncidentStatus.triggered

    fetched = crud.get_incident(session, incident.id)
    assert fetched is not None
    assert fetched.title == "CPU High"


def test_update_incident_status(session: Session):
    incident = crud.create_incident(session, title="Disk Full")
    updated = crud.update_incident_status(session, incident.id, IncidentStatus.acknowledged)
    assert updated is not None
    assert updated.status == IncidentStatus.acknowledged


def test_update_incident_status_not_found(session: Session):
    result = crud.update_incident_status(session, "bad-id", IncidentStatus.resolved)
    assert result is None


def test_list_incidents_all(session: Session):
    crud.create_incident(session, title="A")
    crud.create_incident(session, title="B")
    incidents = crud.list_incidents(session)
    assert len(incidents) == 2


def test_list_incidents_by_status(session: Session):
    inc = crud.create_incident(session, title="A")
    crud.create_incident(session, title="B")
    crud.update_incident_status(session, inc.id, IncidentStatus.acknowledged)

    triggered = crud.list_incidents(session, status=IncidentStatus.triggered)
    acknowledged = crud.list_incidents(session, status=IncidentStatus.acknowledged)
    assert len(triggered) == 1
    assert len(acknowledged) == 1
