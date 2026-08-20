import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlmodel import Session

from vigil import crud
from vigil.config import settings
from vigil.database import get_session
from vigil.models import EscalationPolicy, EscalationStep, Incident, IncidentNote, IncidentStatus, Priority, Schedule, User
from vigil.services import escalation, notifier

router = APIRouter(prefix="/api/v1", tags=["api"])
_logger = logging.getLogger(__name__)


def _ai_initial_response(
    incident_id: str,
    agent: object,
    assigned_user_id: str | None,
    first_timeout: int,
) -> None:
    """バックグラウンドで AI 初動調査を実行し、結果に応じてエスカレーションを判断する。"""
    from sqlmodel import Session

    from vigil import crud
    from vigil.database import engine
    from vigil.models import IncidentStatus
    from vigil.services import escalation, notifier

    with Session(engine) as session:
        incident = crud.get_incident(session, incident_id)
        if incident is None or incident.status != IncidentStatus.triggered:
            return
        try:
            result = agent.investigate_with_recommendation(incident)  # type: ignore[attr-defined]
            crud.add_note(
                session,
                incident_id=incident_id,
                body=f"## AI 初動調査レポート\n\n{result.report}",
            )
            if result.escalate:
                _logger.info("AI: エスカレーション推奨 → 担当者に通知 (incident %s)", incident_id)
                user = crud.get_user(session, assigned_user_id) if assigned_user_id else None
                notifier.send_alert(incident, user)
                escalation.schedule_escalation(incident_id, first_timeout)
            else:
                _logger.info("AI: エスカレーション不要 → フォールバックタイマー設定 (incident %s)", incident_id)
                escalation.schedule_escalation(incident_id, first_timeout * 3)
        except Exception:
            _logger.exception("AI 初動調査失敗。通常エスカレーションに切り替え (incident %s)", incident_id)
            user = crud.get_user(session, assigned_user_id) if assigned_user_id else None
            notifier.send_alert(incident, user)
            escalation.schedule_escalation(incident_id, first_timeout)


class AlertIn(BaseModel):
    title: str
    description: str = ""
    source: str = ""
    team_name: str = "default"
    priority: Priority = Priority.P3


class InvestigationOut(BaseModel):
    incident_id: str
    report: str


class UserIn(BaseModel):
    name: str
    slack_user_id: str = ""
    email: str = ""
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""


class OncallIn(BaseModel):
    current_user_id: str
    rotation_interval: str = "weekly"


class NoteIn(BaseModel):
    body: str
    author_user_id: Optional[str] = None


class PolicyIn(BaseModel):
    name: str
    team_name: str


class StepIn(BaseModel):
    user_id: str
    timeout_minutes: int


class ResolveBySourceIn(BaseModel):
    source: str


# ---- Alerts ----

@router.post("/alerts", response_model=Incident, status_code=201)
async def receive_alert(
    body: AlertIn,
    response: Response,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
) -> Incident:
    fingerprint = crud.compute_fingerprint(body.source, body.title)
    existing = crud.find_active_by_fingerprint(session, fingerprint)
    if existing:
        from vigil.models import _utcnow  # noqa: PLC0415
        existing.updated_at = _utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        response.status_code = 200
        return existing

    schedule = crud.get_schedule_by_team(session, body.team_name)
    assigned_user_id = schedule.current_user_id if schedule else None
    policy = crud.get_policy_by_team(session, body.team_name)
    incident = crud.create_incident(
        session,
        title=body.title,
        description=body.description,
        source=body.source,
        assigned_user_id=assigned_user_id,
        priority=body.priority,
        fingerprint=fingerprint,
        policy_id=policy.id if policy else None,
    )
    user = crud.get_user(session, assigned_user_id) if assigned_user_id else None
    if policy:
        steps = crud.get_steps_for_policy(session, policy.id)
        first_timeout = steps[0].timeout_minutes if steps else settings.escalation_timeout_minutes
    else:
        first_timeout = settings.escalation_timeout_minutes

    agent = getattr(request.app.state, "ai_agent", None)
    if agent is not None:
        # AI が初動対応: 調査結果に応じてエスカレーションを判断
        background_tasks.add_task(
            _ai_initial_response, incident.id, agent, assigned_user_id, first_timeout
        )
    else:
        # AI なし: 従来の即時通知・エスカレーション
        background_tasks.add_task(notifier.send_alert, incident, user)
        escalation.schedule_escalation(incident.id, first_timeout)
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


@router.post("/incidents/resolve-by-source", response_model=list[Incident])
def resolve_incidents_by_source(
    body: ResolveBySourceIn,
    session: Session = Depends(get_session),
) -> list[Incident]:
    incidents = crud.resolve_by_source(session, body.source)
    for inc in incidents:
        escalation.cancel_escalation(inc.id)
    return incidents


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


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigationOut)
def investigate_incident(
    incident_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> InvestigationOut:
    incident = crud.get_incident(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    agent = getattr(request.app.state, "ai_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="AI エージェントが無効です (AI_ENABLED=true を設定してください)",
        )
    try:
        report = agent.investigate(incident)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"調査エラー: {exc}") from exc
    return InvestigationOut(incident_id=incident_id, report=report)


@router.post("/incidents/{incident_id}/resolve", response_model=Incident)
def resolve_incident(
    incident_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Incident:
    incident = crud.update_incident_status(session, incident_id, IncidentStatus.resolved)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    escalation.cancel_escalation(incident_id)
    topology_client = getattr(request.app.state, "topology_client", None)
    if topology_client is not None:
        background_tasks.add_task(topology_client.resolve_for_incident, incident)
    return incident


# ---- Users ----

@router.post("/users", response_model=User, status_code=201)
def create_user(
    body: UserIn,
    session: Session = Depends(get_session),
) -> User:
    return crud.create_user(
        session,
        name=body.name,
        slack_user_id=body.slack_user_id,
        email=body.email,
        slack_webhook_url=body.slack_webhook_url,
        discord_webhook_url=body.discord_webhook_url,
    )


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


# ---- Escalation Policies ----

@router.post("/policies", response_model=EscalationPolicy, status_code=201)
def create_policy(
    body: PolicyIn,
    session: Session = Depends(get_session),
) -> EscalationPolicy:
    return crud.create_policy(session, name=body.name, team_name=body.team_name)


@router.get("/policies/{team_name}", response_model=EscalationPolicy)
def get_policy(
    team_name: str,
    session: Session = Depends(get_session),
) -> EscalationPolicy:
    policy = crud.get_policy_by_team(session, team_name)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/policies/{policy_id}/steps", response_model=EscalationStep, status_code=201)
def add_step(
    policy_id: str,
    body: StepIn,
    session: Session = Depends(get_session),
) -> EscalationStep:
    if crud.get_policy(session, policy_id) is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return crud.add_step(session, policy_id=policy_id, user_id=body.user_id, timeout_minutes=body.timeout_minutes)


@router.get("/policies/{policy_id}/steps", response_model=list[EscalationStep])
def list_steps(
    policy_id: str,
    session: Session = Depends(get_session),
) -> list[EscalationStep]:
    if crud.get_policy(session, policy_id) is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return crud.get_steps_for_policy(session, policy_id)


# ---- Incident Notes ----

@router.post("/incidents/{incident_id}/notes", response_model=IncidentNote, status_code=201)
def add_note(
    incident_id: str,
    body: NoteIn,
    session: Session = Depends(get_session),
) -> IncidentNote:
    if crud.get_incident(session, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return crud.add_note(session, incident_id=incident_id, body=body.body, author_user_id=body.author_user_id)


@router.get("/incidents/{incident_id}/notes", response_model=list[IncidentNote])
def list_notes(
    incident_id: str,
    session: Session = Depends(get_session),
) -> list[IncidentNote]:
    if crud.get_incident(session, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return crud.list_notes(session, incident_id)
