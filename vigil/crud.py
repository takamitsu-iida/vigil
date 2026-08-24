from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from vigil.models import EscalationPolicy, EscalationStep, Incident, IncidentNote, IncidentStatus, Priority, Schedule, User


def compute_fingerprint(source: str, title: str) -> str:
    import hashlib
    raw = f"{source.strip().lower()}:{title.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def find_active_by_fingerprint(session: Session, fingerprint: str) -> Optional[Incident]:
    return session.exec(
        select(Incident)
        .where(Incident.fingerprint == fingerprint)
        .where(Incident.status.in_([IncidentStatus.triggered, IncidentStatus.acknowledged]))
    ).first()


# ---------- User ----------

def get_user(session: Session, user_id: str) -> Optional[User]:
    return session.get(User, user_id)


def create_user(
    session: Session,
    name: str,
    slack_webhook_url: str = "",
    discord_webhook_url: str = "",
) -> User:
    user = User(
        name=name,
        slack_webhook_url=slack_webhook_url,
        discord_webhook_url=discord_webhook_url,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def list_users(session: Session) -> list[User]:
    return list(session.exec(select(User)).all())


# ---------- Schedule ----------

def get_schedule_by_team(session: Session, team_name: str) -> Optional[Schedule]:
    return session.exec(select(Schedule).where(Schedule.team_name == team_name)).first()


def create_schedule(
    session: Session,
    team_name: str,
    current_user_id: str,
    rotation_interval: str = "weekly",
) -> Schedule:
    schedule = Schedule(team_name=team_name, current_user_id=current_user_id, rotation_interval=rotation_interval)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


def update_oncall_user(session: Session, team_name: str, new_user_id: str) -> Optional[Schedule]:
    schedule = get_schedule_by_team(session, team_name)
    if schedule is None:
        return None
    schedule.current_user_id = new_user_id
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


def list_schedules(session: Session) -> list[Schedule]:
    return list(session.exec(select(Schedule)).all())


# ---------- Incident ----------

def create_incident(
    session: Session,
    title: str,
    description: str = "",
    source: str = "",
    assigned_user_id: Optional[str] = None,
    priority: Priority = Priority.P3,
    fingerprint: Optional[str] = None,
    policy_id: Optional[str] = None,
) -> Incident:
    incident = Incident(
        title=title,
        description=description,
        source=source,
        assigned_user_id=assigned_user_id,
        priority=priority,
        fingerprint=fingerprint,
        policy_id=policy_id,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def get_incident(session: Session, incident_id: str) -> Optional[Incident]:
    return session.get(Incident, incident_id)


def update_incident_status(
    session: Session, incident_id: str, status: IncidentStatus
) -> Optional[Incident]:
    from vigil.models import _utcnow  # noqa: PLC0415

    incident = session.get(Incident, incident_id)
    if incident is None:
        return None
    incident.status = status
    incident.updated_at = _utcnow()
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def acknowledge_incident(
    session: Session, incident_id: str, user_id: Optional[str] = None
) -> Optional[Incident]:
    from vigil.models import _utcnow  # noqa: PLC0415

    incident = session.get(Incident, incident_id)
    if incident is None:
        return None
    incident.status = IncidentStatus.acknowledged
    incident.acknowledged_by_user_id = user_id
    incident.updated_at = _utcnow()
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def list_incidents(
    session: Session,
    status: Optional[IncidentStatus] = None,
    since: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Incident]:
    stmt = select(Incident)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if since is not None:
        stmt = stmt.where(Incident.created_at >= since)
    stmt = stmt.order_by(Incident.created_at.desc()).offset(offset).limit(limit)
    return list(session.exec(stmt).all())


def resolve_by_source(session: Session, source: str) -> list[Incident]:
    """source 一致の triggered/acknowledged インシデントを一括 RESOLVED にして返す。"""
    from vigil.models import _utcnow  # noqa: PLC0415
    now = _utcnow()
    incidents = list(session.exec(
        select(Incident)
        .where(Incident.source == source)
        .where(Incident.status.in_([IncidentStatus.triggered, IncidentStatus.acknowledged]))
    ).all())
    for inc in incidents:
        inc.status = IncidentStatus.resolved
        inc.updated_at = now
        session.add(inc)
    if incidents:
        session.commit()
        for inc in incidents:
            session.refresh(inc)
    return incidents


# ---------- EscalationPolicy ----------

def create_policy(session: Session, name: str, team_name: str) -> EscalationPolicy:
    policy = EscalationPolicy(name=name, team_name=team_name)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def get_policy(session: Session, policy_id: str) -> Optional[EscalationPolicy]:
    return session.get(EscalationPolicy, policy_id)


def get_policy_by_team(session: Session, team_name: str) -> Optional[EscalationPolicy]:
    return session.exec(select(EscalationPolicy).where(EscalationPolicy.team_name == team_name)).first()


def add_step(
    session: Session,
    policy_id: str,
    user_id: str,
    timeout_minutes: int,
) -> EscalationStep:
    existing_count = len(get_steps_for_policy(session, policy_id))
    step = EscalationStep(
        policy_id=policy_id,
        step_order=existing_count + 1,
        user_id=user_id,
        timeout_minutes=timeout_minutes,
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def get_steps_for_policy(session: Session, policy_id: str) -> list[EscalationStep]:
    return list(
        session.exec(
            select(EscalationStep)
            .where(EscalationStep.policy_id == policy_id)
            .order_by(EscalationStep.step_order)
        ).all()
    )


# ---------- IncidentNote ----------

def add_note(
    session: Session,
    incident_id: str,
    body: str,
    author_user_id: Optional[str] = None,
) -> IncidentNote:
    note = IncidentNote(incident_id=incident_id, body=body, author_user_id=author_user_id)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


def list_notes(session: Session, incident_id: str) -> list[IncidentNote]:
    return list(
        session.exec(
            select(IncidentNote)
            .where(IncidentNote.incident_id == incident_id)
            .order_by(IncidentNote.created_at)
        ).all()
    )
