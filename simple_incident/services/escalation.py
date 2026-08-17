import logging

logger = logging.getLogger(__name__)


def schedule_escalation(incident_id: str, timeout_minutes: int) -> None:
    # Phase 4で実装: APSchedulerによるエスカレーションタイマー登録
    logger.info("schedule_escalation stub: incident=%s timeout=%dmin", incident_id, timeout_minutes)


def cancel_escalation(incident_id: str) -> None:
    # Phase 4で実装: エスカレーションタイマーのキャンセル
    logger.info("cancel_escalation stub: incident=%s", incident_id)
