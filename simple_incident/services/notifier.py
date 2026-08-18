import logging
from typing import Optional

import httpx

from simple_incident.config import settings
from simple_incident.models import Incident, User

logger = logging.getLogger(__name__)


async def send_alert(incident: Incident, user: Optional[User]) -> None:
    """Slack/Discord Webhook にアラートを送信する。URL未設定の場合はログのみ。"""
    assigned = user.name if user else "(未割当)"
    text = (
        f"[{incident.status.upper()}] {incident.title}\n"
        f"説明: {incident.description}\n"
        f"担当者: {assigned}\n"
        f"ID: {incident.id}"
    )

    async with httpx.AsyncClient() as client:
        if settings.slack_webhook_url:
            await _post_webhook(client, settings.slack_webhook_url, {"text": text})
        else:
            logger.info("Slack webhook not configured, skipping. incident=%s", incident.id)

        if settings.discord_webhook_url:
            await _post_webhook(client, settings.discord_webhook_url, {"content": text})
        else:
            logger.info("Discord webhook not configured, skipping. incident=%s", incident.id)


async def _post_webhook(client: httpx.AsyncClient, url: str, payload: dict) -> None:
    try:
        res = await client.post(url, json=payload, timeout=10.0)
        res.raise_for_status()
        logger.info("Webhook sent status=%d url=%s", res.status_code, url)
    except httpx.HTTPError as exc:
        logger.error("Webhook request failed url=%s error=%s", url, exc)
