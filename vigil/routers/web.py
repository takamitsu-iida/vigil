from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from vigil import crud
from vigil.config import settings
from vigil.database import get_session
from vigil.models import IncidentStatus, Priority
from vigil.services import escalation, notifier

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="vigil/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    incidents = crud.list_incidents(session)
    users_by_id = {u.id: u.name for u in crud.list_users(session)}
    return templates.TemplateResponse(
        request, "index.html", {"incidents": incidents, "users_by_id": users_by_id}
    )


@router.get("/incidents/new", response_class=HTMLResponse)
def new_incident_form(request: Request, session: Session = Depends(get_session)):
    schedules = crud.list_schedules(session)
    teams = sorted({s.team_name for s in schedules}) or ["default"]
    return templates.TemplateResponse(
        request, "create_incident.html", {"teams": teams}
    )


@router.post("/incidents/new")
async def web_create_incident(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(),
    description: str = Form(""),
    source: str = Form("manual"),
    team_name: str = Form("default"),
    priority: str = Form("P3"),
    session: Session = Depends(get_session),
):
    from vigil.routers.api import _ai_initial_response  # 循環しない方向の import

    fingerprint = crud.compute_fingerprint(source, title)
    existing = crud.find_active_by_fingerprint(session, fingerprint)
    if existing:
        return Response(status_code=200, headers={"HX-Redirect": f"/incidents/{existing.id}"})

    schedule = crud.get_schedule_by_team(session, team_name)
    assigned_user_id = schedule.current_user_id if schedule else None
    policy = crud.get_policy_by_team(session, team_name)
    incident = crud.create_incident(
        session,
        title=title,
        description=description,
        source=source,
        assigned_user_id=assigned_user_id,
        priority=Priority(priority),
        fingerprint=fingerprint,
        policy_id=policy.id if policy else None,
    )

    if policy:
        steps = crud.get_steps_for_policy(session, policy.id)
        first_timeout = steps[0].timeout_minutes if steps else settings.escalation_timeout_minutes
    else:
        first_timeout = settings.escalation_timeout_minutes

    agent = getattr(request.app.state, "ai_agent", None)
    if agent is not None:
        background_tasks.add_task(
            _ai_initial_response, incident.id, agent, assigned_user_id, first_timeout
        )
    else:
        user = crud.get_user(session, assigned_user_id) if assigned_user_id else None
        background_tasks.add_task(notifier.send_alert, incident, user)
        escalation.schedule_escalation(incident.id, first_timeout)

    return Response(status_code=200, headers={"HX-Redirect": f"/incidents/{incident.id}"})


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
def incident_detail(incident_id: str, request: Request, session: Session = Depends(get_session)):
    incident = crud.get_incident(session, incident_id)
    if incident is None:
        return templates.TemplateResponse(request, "404.html", status_code=404)
    assigned_user = crud.get_user(session, incident.assigned_user_id) if incident.assigned_user_id else None
    notes = crud.list_notes(session, incident_id)
    users = {u.id: u.name for u in crud.list_users(session)}
    return templates.TemplateResponse(
        request, "incident_detail.html",
        {"incident": incident, "assigned_user": assigned_user, "notes": notes, "users_by_id": users}
    )


@router.post("/incidents/{incident_id}/acknowledge")
def web_acknowledge(incident_id: str, session: Session = Depends(get_session)):
    crud.update_incident_status(session, incident_id, IncidentStatus.acknowledged)
    escalation.cancel_escalation(incident_id)
    return Response(status_code=200, headers={"HX-Redirect": f"/incidents/{incident_id}"})


@router.post("/incidents/{incident_id}/notes")
def web_add_note(
    incident_id: str,
    body: str = Form(),
    session: Session = Depends(get_session),
):
    crud.add_note(session, incident_id=incident_id, body=body)
    return Response(status_code=200, headers={"HX-Redirect": f"/incidents/{incident_id}"})


@router.post("/incidents/{incident_id}/resolve")
def web_resolve(
    incident_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    incident = crud.update_incident_status(session, incident_id, IncidentStatus.resolved)
    if incident is not None:
        escalation.cancel_escalation(incident_id)
        topology_client = getattr(request.app.state, "topology_client", None)
        if topology_client is not None:
            background_tasks.add_task(topology_client.resolve_for_incident, incident)
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
