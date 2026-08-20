"""topology-syslog からのインシデント詳細情報取得クライアント。

vigil インシデントのタイトルに含まれる "[INC-YYYYMMDD-NNN]" を検出し、
topology-syslog の REST API から詳細（生ログ・二次影響ノード等）を取得する。
"""
from __future__ import annotations

import logging
import re

import httpx

from vigil.models import Incident

_logger = logging.getLogger(__name__)
_TOPO_ID_RE = re.compile(r'\[(INC-[^\]]+)\]')


def extract_topology_incident_id(title: str) -> str | None:
    """タイトルから topology-syslog インシデント ID を抽出する。"""
    m = _TOPO_ID_RE.search(title)
    return m.group(1) if m else None


class TopologySyslogClient:
    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_detail_text(self, incident: Incident) -> str | None:
        """vigil インシデントに対応する topology-syslog の詳細テキストを返す。"""
        topo_id = extract_topology_incident_id(incident.title)
        if not topo_id:
            return None
        try:
            resp = httpx.get(
                f"{self._base_url}/incidents/{topo_id}",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            _logger.warning("topology-syslog 詳細取得失敗 (%s): %s", topo_id, exc)
            return None

        lines = [
            f"topology-syslog インシデント ID: {data.get('incident_id')}",
            f"根本原因ノード: {data.get('root_cause_node')}",
            f"主要イベント: {data.get('primary_event')}",
            f"二次影響ノード: {', '.join(data.get('secondary_nodes', []))}",
            f"関連ログ数: {data.get('raw_log_count')}",
            f"ステータス: {data.get('status')}",
            f"ネットワーク状況: {data.get('condition')}",
            f"再発回数: {data.get('recurrence_count', 0)}",
        ]
        for log in data.get("raw_logs", [])[:10]:
            lines.append(f"  ログ: {log}")
        return "\n".join(lines)

    def get_report(self, incident: Incident) -> str | None:
        """topology-syslog の AI レポートを取得する。未生成の場合は生成して返す。"""
        topo_id = extract_topology_incident_id(incident.title)
        if not topo_id:
            return None
        try:
            resp = httpx.post(
                f"{self._base_url}/incidents/{topo_id}/report",
                timeout=30.0,  # LLM 内部生成を待つため長めに設定
            )
            resp.raise_for_status()
            return resp.json().get("report")
        except Exception as exc:
            _logger.warning("topology-syslog AI レポート取得失敗 (%s): %s", topo_id, exc)
            return None

    def resolve_incident(self, topo_incident_id: str) -> None:
        """topology-syslog の指定インシデントを RESOLVED にする。失敗してもログのみ。"""
        try:
            resp = httpx.put(
                f"{self._base_url}/incidents/{topo_incident_id}/resolve",
                timeout=self._timeout,
            )
            if resp.status_code not in (200, 404):
                resp.raise_for_status()
        except Exception as exc:
            _logger.warning("topology-syslog resolve 失敗 (%s): %s", topo_incident_id, exc)

    def resolve_for_incident(self, incident: Incident) -> None:
        """vigil インシデントのタイトルから topology-syslog インシデントを特定して RESOLVED にする。"""
        topo_id = extract_topology_incident_id(incident.title)
        if topo_id:
            self.resolve_incident(topo_id)
