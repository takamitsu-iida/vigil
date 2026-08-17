from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from simple_incident import crud
from simple_incident.config import settings
from simple_incident.database import get_session
from simple_incident.models import Incident, IncidentStatus, Schedule, User
from simple_incident.services import escalation, notifier

router = APIRouter(prefix="/api/v1", tags=["api"])


class AlertIn(BaseModel):
    title: str
    description: str = ""
    source: str = ""
    team_name: str = "default"


class UserIn(BaseModel):
    name: str
    slack_user_id: str = ""
    email: str = ""


class OncallIn(BaseModel):
    current_user_id: str
    rotation_interval: str = "weekly"


# ---- Alerts ----

@router.post("/alerts", response_model=Incident, status_code=201)
async def receive_alert(
    body: AlertIn,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Incident:
    schedule = crud.get_schedule_by_team(session, body.team_name)
    assigned_user_id = schedule.current_user_id if schedule else None
    incident = crud.create_incident(
        session,
        title=body.title,
        description=body.description,
        assigned_user_id=assigned_user_id,
    )
    user = crud.get_user(session, assigned_user_id) if assigned_user_id else None
    background_tasks.add_task(notifier.send_alert, incident, user)
    escalation.schedule_escalation(incident.id, settings.escalation_timeout_minutes)
    return incident


# ---- Incidents ----

@router.get("/incidents", response_model=list[Incident])
def list_incidents(
    status: Optional[IncidentStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[Incident]:
    return crud.list_incidents(session, status=status, limit=limit, offset=offset)


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: str,
    session: Session = Depends(get_session),
) -> Incident:
    incident = crud.get_incident(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/acknowledge", response_model=Incident)
def acknowledge_incident(
    incident_id: str,
    session: Session = Depends(get_session),
) -> Incident:
    incident = crud.update_incident_status(session, incident_id, IncidentStatus.acknowledged)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    escalation.cancel_escalation(incident_id)
    return incident


@router.post("/incidents/{incident_id}/resolve", response_model=Incident)
def resolve_incident(
    incident_id: str,
    session: Session = Depends(get_session),
) -> Incident:
    incident = crud.update_incident_status(session, incident_id, IncidentStatus.resolved)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    escalation.cancel_escalation(incident_id)
    return incident


# ---- Users ----

@router.post("/users", response_model=User, status_code=201)
def create_user(
    body: UserIn,
    session: Session = Depends(get_session),
) -> User:
    return crud.create_user(session, name=body.name, slack_user_id=body.slack_user_id, email=body.email)


@router.get("/users", response_model=list[User])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    return crud.list_users(session)


# ---- Schedules ----

@router.put("/schedules/{team_name}/oncall", response_model=Schedule)
def update_oncall(
    team_name: str,
    body: OncallIn,
    session: Session = Depends(get_session),
) -> Schedule:
    existing = crud.get_schedule_by_team(session, team_name)
    if existing is None:
        return crud.create_schedule(
            session,
            team_name=team_name,
            current_user_id=body.current_user_id,
            rotation_interval=body.rotation_interval,
        )
    updated = crud.update_oncall_user(session, team_name, body.current_user_id)
    assert updated is not None
    return updated
