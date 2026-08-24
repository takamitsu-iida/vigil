import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class IncidentStatus(str, Enum):
    triggered = "triggered"
    acknowledged = "acknowledged"
    resolved = "resolved"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class User(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    name: str
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""


class Schedule(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    team_name: str
    current_user_id: str = Field(foreign_key="user.id")
    rotation_interval: str = "weekly"


class EscalationPolicy(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    name: str
    team_name: str = Field(index=True)


class EscalationStep(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    policy_id: str = Field(foreign_key="escalationpolicy.id")
    step_order: int
    user_id: str = Field(foreign_key="user.id")
    timeout_minutes: int


class Incident(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    title: str
    description: str = ""
    status: IncidentStatus = IncidentStatus.triggered
    priority: Priority = Priority.P3
    source: str = Field(default="", index=True)
    fingerprint: Optional[str] = Field(default=None, index=True)
    assigned_user_id: Optional[str] = Field(default=None, foreign_key="user.id")
    acknowledged_by_user_id: Optional[str] = Field(default=None, foreign_key="user.id")
    policy_id: Optional[str] = Field(default=None, foreign_key="escalationpolicy.id")
    escalation_step: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class IncidentNote(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    author_user_id: Optional[str] = Field(default=None, foreign_key="user.id")
    body: str
    created_at: datetime = Field(default_factory=_utcnow)
