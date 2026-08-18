import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from simple_incident.models import IncidentStatus

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def schedule_escalation(incident_id: str, timeout_minutes: int) -> None:
    job_id = f"esc_{incident_id}"
    # 未起動状態では replace_existing が pending リストに効かないため手動で削除する
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()
    scheduler.add_job(
        _escalate,
        trigger="interval",
        minutes=timeout_minutes,
        id=job_id,
        args=[incident_id],
        max_instances=1,
    )
    logger.info("Escalation scheduled: incident=%s timeout=%dmin", incident_id, timeout_minutes)


def cancel_escalation(incident_id: str) -> None:
    job_id = f"esc_{incident_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Escalation cancelled: incident=%s", incident_id)


async def _escalate(incident_id: str) -> None:
    """エスカレーションジョブ: triggered のままなら再通知する。"""
    from sqlmodel import Session

    from simple_incident import crud
    from simple_incident.database import engine
    from simple_incident.services import notifier

    with Session(engine) as session:
        incident = crud.get_incident(session, incident_id)
        if incident is None or incident.status != IncidentStatus.triggered:
            cancel_escalation(incident_id)
            return
        user = crud.get_user(session, incident.assigned_user_id) if incident.assigned_user_id else None

    logger.warning("Escalating incident=%s (still triggered)", incident_id)
    await notifier.send_alert(incident, user)
