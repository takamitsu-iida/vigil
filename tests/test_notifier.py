from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vigil.config import settings
from vigil.models import Incident, IncidentStatus, User
from vigil.services.notifier import send_alert


def _make_incident(**kwargs) -> Incident:
    defaults = dict(
        id="test-inc-id",
        title="CPU High",
        description="usage 90%",
        status=IncidentStatus.triggered,
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def _make_user(**kwargs) -> User:
    defaults = dict(id="user-id", name="Alice", email="alice@example.com")
    defaults.update(kwargs)
    return User(**defaults)


def _mock_async_client(status_code: int = 200):
    """httpx.AsyncClient をモックして post が呼ばれたことを検証できるようにする。"""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    return ctx, mock_client


async def test_send_alert_posts_to_slack(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/test")
    monkeypatch.setattr(settings, "discord_webhook_url", "")

    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), _make_user())

    mock_client.post.assert_called_once()
    url, *_ = mock_client.post.call_args.args
    assert "hooks.slack.com" in url


async def test_send_alert_posts_to_discord(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    monkeypatch.setattr(settings, "discord_webhook_url", "https://discord.com/api/webhooks/test")

    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), _make_user())

    mock_client.post.assert_called_once()
    url, *_ = mock_client.post.call_args.args
    assert "discord.com" in url


async def test_send_alert_posts_to_both(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/test")
    monkeypatch.setattr(settings, "discord_webhook_url", "https://discord.com/api/webhooks/test")

    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), _make_user())

    assert mock_client.post.call_count == 2


async def test_send_alert_skips_when_no_webhooks_configured(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    monkeypatch.setattr(settings, "discord_webhook_url", "")

    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), None)

    mock_client.post.assert_not_called()


async def test_send_alert_includes_incident_info_in_payload(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/test")
    monkeypatch.setattr(settings, "discord_webhook_url", "")

    ctx, mock_client = _mock_async_client()
    incident = _make_incident(title="Disk Full", description="100%")
    user = _make_user(name="Bob")

    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(incident, user)

    payload = mock_client.post.call_args.kwargs["json"]
    assert "Disk Full" in payload["text"]
    assert "Bob" in payload["text"]


async def test_send_alert_shows_unassigned_when_no_user(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/test")
    monkeypatch.setattr(settings, "discord_webhook_url", "")

    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), None)

    payload = mock_client.post.call_args.kwargs["json"]
    assert "未割当" in payload["text"]


async def test_send_alert_continues_on_http_error(monkeypatch):
    """Webhook 送信失敗時も例外を伝播させない。"""
    import httpx as _httpx

    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/test")
    monkeypatch.setattr(settings, "discord_webhook_url", "")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_httpx.ConnectError("connection refused"))

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), _make_user())  # 例外を送出しないこと


async def test_send_alert_uses_user_discord_webhook(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    monkeypatch.setattr(settings, "discord_webhook_url", "https://discord.com/api/webhooks/global")

    user = _make_user(discord_webhook_url="https://discord.com/api/webhooks/personal")
    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), user)

    url, *_ = mock_client.post.call_args.args
    assert "personal" in url


async def test_send_alert_uses_user_slack_webhook(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.com/global")
    monkeypatch.setattr(settings, "discord_webhook_url", "")

    user = _make_user(slack_webhook_url="https://hooks.slack.com/personal")
    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), user)

    url, *_ = mock_client.post.call_args.args
    assert "personal" in url


async def test_send_alert_falls_back_to_global_when_user_has_no_webhook(monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    monkeypatch.setattr(settings, "discord_webhook_url", "https://discord.com/api/webhooks/global")

    user = _make_user()  # discord_webhook_url is empty
    ctx, mock_client = _mock_async_client()
    with patch("vigil.services.notifier.httpx.AsyncClient", return_value=ctx):
        await send_alert(_make_incident(), user)

    url, *_ = mock_client.post.call_args.args
    assert "global" in url
