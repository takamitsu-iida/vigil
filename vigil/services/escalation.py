import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from vigil.models import IncidentStatus

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def schedule_escalation(incident_id: str, timeout_minutes: int) -> None:
    job_id = f"esc_{incident_id}"
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()
    run_date = datetime.now() + timedelta(minutes=timeout_minutes)
    scheduler.add_job(
        _escalate,
        trigger="date",
        run_date=run_date,
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
    """エスカレーションジョブ: ポリシーのステップ順に通知し、次ステップを再スケジュールする。"""
    from sqlmodel import Session

    from vigil import crud
    from vigil.config import settings as _settings
    from vigil.database import engine
    from vigil.models import _utcnow
    from vigil.services import notifier

    with Session(engine) as session:
        incident = crud.get_incident(session, incident_id)
        if incident is None or incident.status != IncidentStatus.triggered:
            cancel_escalation(incident_id)
            return

        if incident.policy_id:
            steps = crud.get_steps_for_policy(session, incident.policy_id)
        else:
            steps = []

        if steps:
            # 現在のステップ (範囲外は最終ステップに固定)
            step_idx = min(incident.escalation_step, len(steps) - 1)
            step = steps[step_idx]
            user = crud.get_user(session, step.user_id)

            # 次ステップへ進める (最終ステップは固定)
            next_idx = min(step_idx + 1, len(steps) - 1)
            incident.escalation_step = next_idx
            incident.updated_at = _utcnow()
            session.add(incident)
            session.commit()
            # commit 後に両オブジェクトを再ロードしてから detach する
            session.refresh(incident)
            if user is not None:
                session.refresh(user)

            next_timeout = steps[next_idx].timeout_minutes
        else:
            # ポリシーなし: 担当者に再通知し同じ間隔で繰り返す
            user = crud.get_user(session, incident.assigned_user_id) if incident.assigned_user_id else None
            next_timeout = _settings.escalation_timeout_minutes

        # session を抜けた後も属性にアクセスできるよう明示的にデタッチ
        if user is not None:
            session.expunge(user)
        session.expunge(incident)

    logger.warning("Escalating incident=%s", incident_id)
    await notifier.send_alert(incident, user)
    schedule_escalation(incident_id, next_timeout)
