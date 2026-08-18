from typing import Optional

from sqlmodel import Session, select

from simple_incident.models import Incident, IncidentStatus, Schedule, User


# ---------- User ----------

def get_user(session: Session, user_id: str) -> Optional[User]:
    return session.get(User, user_id)


def create_user(session: Session, name: str, slack_user_id: str = "", email: str = "") -> User:
    user = User(name=name, slack_user_id=slack_user_id, email=email)
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
    assigned_user_id: Optional[str] = None,
) -> Incident:
    incident = Incident(title=title, description=description, assigned_user_id=assigned_user_id)
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def get_incident(session: Session, incident_id: str) -> Optional[Incident]:
    return session.get(Incident, incident_id)


def update_incident_status(
    session: Session, incident_id: str, status: IncidentStatus
) -> Optional[Incident]:
    from simple_incident.models import _utcnow  # noqa: PLC0415

    incident = session.get(Incident, incident_id)
    if incident is None:
        return None
    incident.status = status
    incident.updated_at = _utcnow()
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def list_incidents(
    session: Session,
    status: Optional[IncidentStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Incident]:
    stmt = select(Incident)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    stmt = stmt.offset(offset).limit(limit)
    return list(session.exec(stmt).all())
