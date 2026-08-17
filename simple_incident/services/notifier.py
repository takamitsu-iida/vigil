import logging
from typing import Optional

from simple_incident.models import Incident, User

logger = logging.getLogger(__name__)


async def send_alert(incident: Incident, user: Optional[User]) -> None:
    # Phase 4で実装: Slack/Discord Webhook送信
    logger.info("send_alert stub: incident=%s user=%s", incident.id, user.id if user else None)
