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


class User(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    name: str
    slack_user_id: str = ""
    email: str = ""


class Schedule(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    team_name: str
    current_user_id: str = Field(foreign_key="user.id")
    rotation_interval: str = "weekly"


class Incident(SQLModel, table=True):
    id: str = Field(default_factory=_new_uuid, primary_key=True)
    title: str
    description: str = ""
    status: IncidentStatus = IncidentStatus.triggered
    assigned_user_id: Optional[str] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
