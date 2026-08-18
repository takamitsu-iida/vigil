from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from simple_incident import crud
from simple_incident.database import get_session
from simple_incident.models import IncidentStatus
from simple_incident.services import escalation

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="simple_incident/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    incidents = crud.list_incidents(session)
    users_by_id = {u.id: u.name for u in crud.list_users(session)}
    return templates.TemplateResponse(
        request, "index.html", {"incidents": incidents, "users_by_id": users_by_id}
    )


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
def incident_detail(incident_id: str, request: Request, session: Session = Depends(get_session)):
    incident = crud.get_incident(session, incident_id)
    if incident is None:
        return templates.TemplateResponse(request, "404.html", status_code=404)
    assigned_user = crud.get_user(session, incident.assigned_user_id) if incident.assigned_user_id else None
    return templates.TemplateResponse(
        request, "incident_detail.html", {"incident": incident, "assigned_user": assigned_user}
    )


@router.post("/incidents/{incident_id}/acknowledge")
def web_acknowledge(incident_id: str, session: Session = Depends(get_session)):
    crud.update_incident_status(session, incident_id, IncidentStatus.acknowledged)
    escalation.cancel_escalation(incident_id)
    return Response(status_code=200, headers={"HX-Redirect": f"/incidents/{incident_id}"})


@router.post("/incidents/{incident_id}/resolve")
def web_resolve(incident_id: str, session: Session = Depends(get_session)):
    crud.update_incident_status(session, incident_id, IncidentStatus.resolved)
    escalation.cancel_escalation(incident_id)
    return Response(status_code=200, headers={"HX-Redirect": f"/incidents/{incident_id}"})


@router.get("/schedules", response_class=HTMLResponse)
def schedules_page(request: Request, session: Session = Depends(get_session)):
    schedules = crud.list_schedules(session)
    users = crud.list_users(session)
    users_by_id = {u.id: u.name for u in users}
    return templates.TemplateResponse(
        request, "schedules.html", {"schedules": schedules, "users": users, "users_by_id": users_by_id}
    )


@router.post("/schedules/oncall")
def web_create_oncall(
    team_name: str = Form(),
    current_user_id: str = Form(),
    session: Session = Depends(get_session),
):
    existing = crud.get_schedule_by_team(session, team_name)
    if existing:
        crud.update_oncall_user(session, team_name, current_user_id)
    else:
        crud.create_schedule(session, team_name, current_user_id)
    return Response(status_code=200, headers={"HX-Redirect": "/schedules"})


@router.post("/schedules/{team_name}/oncall")
def web_update_oncall(
    team_name: str,
    current_user_id: str = Form(),
    session: Session = Depends(get_session),
):
    existing = crud.get_schedule_by_team(session, team_name)
    if existing:
        crud.update_oncall_user(session, team_name, current_user_id)
    else:
        crud.create_schedule(session, team_name, current_user_id)
    return Response(status_code=200, headers={"HX-Redirect": "/schedules"})


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, session: Session = Depends(get_session)):
    users = crud.list_users(session)
    return templates.TemplateResponse(
        request, "users.html", {"users": users}
    )


@router.post("/users")
def web_create_user(
    name: str = Form(),
    email: str = Form(""),
    slack_user_id: str = Form(""),
    session: Session = Depends(get_session),
):
    crud.create_user(session, name=name, slack_user_id=slack_user_id, email=email)
    return Response(status_code=200, headers={"HX-Redirect": "/users"})
