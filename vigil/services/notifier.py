import logging
from typing import Optional

import httpx

from vigil.config import settings
from vigil.models import Incident, Priority, User

logger = logging.getLogger(__name__)

_PRIORITY_PREFIX = {
    Priority.P1: "🚨 ",
    Priority.P2: "⚠️ ",
    Priority.P3: "",
    Priority.P4: "",
}
# Slack では <!channel> でチャンネル全体をメンションできる
_SLACK_MENTION = {Priority.P1: "<!channel> ", Priority.P2: "<!channel> "}


async def send_alert(incident: Incident, user: Optional[User]) -> None:
    """Slack/Discord Webhook にアラートを送信する。URL未設定の場合はログのみ。"""
    assigned = user.name if user else "(未割当)"
    prefix = _PRIORITY_PREFIX.get(incident.priority, "")
    text = (
        f"{prefix}[{incident.status.upper()}][{incident.priority.value}] {incident.title}\n"
        f"説明: {incident.description}\n"
        f"担当者: {assigned}\n"
        f"ID: {incident.id}"
    )

    incident_url = f"{settings.base_url}/incidents/{incident.id}"
    text += f"\n詳細・対応: {incident_url}"

    slack_url = (user.slack_webhook_url if user and user.slack_webhook_url else settings.slack_webhook_url)
    discord_url = (user.discord_webhook_url if user and user.discord_webhook_url else settings.discord_webhook_url)

    async with httpx.AsyncClient() as client:
        if slack_url:
            slack_mention = _SLACK_MENTION.get(incident.priority, "")
            await _post_webhook(client, slack_url, {"text": slack_mention + text})
        else:
            logger.info("Slack webhook not configured, skipping. incident=%s", incident.id)

        if discord_url:
            await _post_webhook(client, discord_url, {"content": text})
        else:
            logger.info("Discord webhook not configured, skipping. incident=%s", incident.id)


async def _post_webhook(client: httpx.AsyncClient, url: str, payload: dict) -> None:
    try:
        res = await client.post(url, json=payload, timeout=10.0)
        res.raise_for_status()
        logger.info("Webhook sent status=%d url=%s", res.status_code, url)
    except httpx.HTTPError as exc:
        logger.error("Webhook request failed url=%s error=%s", url, exc)
