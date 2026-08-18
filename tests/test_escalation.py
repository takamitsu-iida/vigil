from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import simple_incident.models  # noqa: F401
from simple_incident import crud
from simple_incident.models import Incident, IncidentStatus, User
from simple_incident.services import escalation
from simple_incident.services.escalation import cancel_escalation, schedule_escalation, scheduler


@pytest.fixture(autouse=True)
def _clean_scheduler():
    """各テスト後にスケジューラのジョブを全削除する。"""
    yield
    for job in scheduler.get_jobs():
        job.remove()


@pytest.fixture(name="mem_engine")
def mem_engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(mem_engine):
    with Session(mem_engine) as session:
        yield session


# ---- schedule / cancel ----

def test_schedule_escalation_adds_job():
    schedule_escalation("inc-1", timeout_minutes=5)
    assert scheduler.get_job("esc_inc-1") is not None


def test_cancel_escalation_removes_job():
    schedule_escalation("inc-2", timeout_minutes=5)
    cancel_escalation("inc-2")
    assert scheduler.get_job("esc_inc-2") is None


def test_cancel_escalation_noop_when_not_scheduled():
    cancel_escalation("nonexistent-id")  # 例外なく終了すること


def test_schedule_escalation_replace_existing():
    schedule_escalation("inc-3", timeout_minutes=5)
    schedule_escalation("inc-3", timeout_minutes=10)  # replace_existing=True なので重複しない
    jobs = [j for j in scheduler.get_jobs() if j.id == "esc_inc-3"]
    assert len(jobs) == 1


# ---- _escalate logic ----

async def test_escalate_sends_alert_when_triggered(session, mem_engine, monkeypatch):
    user = crud.create_user(session, name="Alice")
    incident = crud.create_incident(session, title="CPU High", assigned_user_id=user.id)
    assert incident.status == IncidentStatus.triggered

    mock_send = AsyncMock()
    monkeypatch.setattr("simple_incident.services.notifier.send_alert", mock_send)

    with patch("simple_incident.database.engine", mem_engine):
        await escalation._escalate(incident.id)

    mock_send.assert_awaited_once()
    called_incident, called_user = mock_send.call_args.args
    assert called_incident.id == incident.id
    assert called_user.id == user.id


async def test_escalate_skips_when_acknowledged(session, mem_engine, monkeypatch):
    incident = crud.create_incident(session, title="CPU High")
    crud.update_incident_status(session, incident.id, IncidentStatus.acknowledged)

    mock_send = AsyncMock()
    monkeypatch.setattr("simple_incident.services.notifier.send_alert", mock_send)

    with patch("simple_incident.database.engine", mem_engine):
        await escalation._escalate(incident.id)

    mock_send.assert_not_awaited()


async def test_escalate_skips_when_resolved(session, mem_engine, monkeypatch):
    incident = crud.create_incident(session, title="CPU High")
    crud.update_incident_status(session, incident.id, IncidentStatus.resolved)

    mock_send = AsyncMock()
    monkeypatch.setattr("simple_incident.services.notifier.send_alert", mock_send)

    with patch("simple_incident.database.engine", mem_engine):
        await escalation._escalate(incident.id)

    mock_send.assert_not_awaited()


async def test_escalate_cancels_job_when_acknowledged(session, mem_engine, monkeypatch):
    incident = crud.create_incident(session, title="CPU High")
    crud.update_incident_status(session, incident.id, IncidentStatus.acknowledged)
    schedule_escalation(incident.id, timeout_minutes=5)

    monkeypatch.setattr("simple_incident.services.notifier.send_alert", AsyncMock())

    with patch("simple_incident.database.engine", mem_engine):
        await escalation._escalate(incident.id)

    assert scheduler.get_job(f"esc_{incident.id}") is None


async def test_escalate_no_user_when_unassigned(session, mem_engine, monkeypatch):
    incident = crud.create_incident(session, title="CPU High", assigned_user_id=None)

    mock_send = AsyncMock()
    monkeypatch.setattr("simple_incident.services.notifier.send_alert", mock_send)

    with patch("simple_incident.database.engine", mem_engine):
        await escalation._escalate(incident.id)

    called_incident, called_user = mock_send.call_args.args
    assert called_user is None


async def test_escalate_noop_when_incident_not_found(mem_engine, monkeypatch):
    mock_send = AsyncMock()
    monkeypatch.setattr("simple_incident.services.notifier.send_alert", mock_send)

    with patch("simple_incident.database.engine", mem_engine):
        await escalation._escalate("nonexistent-id")

    mock_send.assert_not_awaited()
