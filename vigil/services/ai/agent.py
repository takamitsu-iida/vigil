"""vigil インシデント AI 調査エージェント。

フロー:
  1. QueryCache を確認（同 fingerprint の過去レポートがあれば即返却）
  2. topology-syslog AI レポートを取得した場合 → 行動指示特化プロンプト
     取得できない場合 → 詳細情報（生ログ等）を取得して汎用プロンプト
  3. RAGStore で類似過去調査を検索
  4. LLM でレポート生成
  5. QueryCache / RAGStore に保存
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from vigil.models import Incident
from vigil.services.ai.llm_client import LLMClient
from vigil.services.ai.query_cache import QueryCache
from vigil.services.ai.rag_store import RAGStore
from vigil.services.ai.topology_client import TopologySyslogClient

_logger = logging.getLogger(__name__)

# LLM 出力のエスカレーション推奨をパースする正規表現
_ESC_RE = re.compile(r'《エスカレーション推奨》\s*[:&#65306;]\s*(YES|NO)', re.IGNORECASE)


@dataclass
class InvestigationResult:
    report: str
    escalate: bool  # True の場合は人間へのエスカレーションを推奨


def _parse_escalation(report: str) -> bool:
    """レポートからエスカレーション推奨を抽出。パターンが見つからなければデフォルトでエスカレーションする。"""
    m = _ESC_RE.search(report)
    return m.group(1).upper() != "NO" if m else True

# topology-syslog AI レポートが利用できる場合—「技術分析」を前提に「行動指示」に特化
_PROMPT_WITH_TOPO_REPORT = """\
あなたはITインシデント対応のプロのAIです。
以下の「network-topology 技術分析」を前提として、オンコールエンジニアへの行動指示レポートを日本語で作成してください。
技術分析の内容は繰り返さず、「次に何をすべきか」に特化してください。

## ネットワーク技術分析（topology-syslog による）
{topology_report}

## インシデント情報（vigil）
{incident_summary}
{similar_section}
## レポート形式（必ず以下の項目を含めること）
1. **状況サマリー** — 技術分析の要点を 1～2 行で（詳細は繰り返さない）
2. **一次対応チェックリスト** — 今すぐ確認・実施すべき項目（番号付き）
3. **確認コマンド** — 診断に使えるコマンド例
4. **エスカレーション判断**（必ず以下の形式で記載）:
   《エスカレーション推奨》: YES または NO
   《推奨理由》: 1行で
5. **顧客・関係者への連絡文面案** — 影響が外部に及ぶ場合の連絡文面
"""

# topology-syslog AI レポートが利用できない場合の汎用プロンプト
_PROMPT_GENERIC = """\
あなたはITインシデント対応の専門家AIです。
以下のインシデントについて、一次対応レポートを日本語で作成してください。

## インシデント情報
{incident_summary}
{topology_section}{similar_section}
## レポート形式（必ず以下の項目を含めること）
1. **状況把握** — 何が起きているか 1〜2 行で
2. **影響範囲の評価** — 影響を受けているサービス/システム
3. **推定原因** — 考えられる原因と根拠
4. **一次対応手順** — 今すぐ取るべき具体的な手順（番号付きリスト）
5. **確認コマンド** — 診断に使えるコマンド例
6. **エスカレーション判断**（必ず以下の形式で記載）:
   《エスカレーション推奨》: YES または NO
   《推奨理由》: 1行で
"""

_TOPOLOGY_DETAIL_TMPL = """
## topology-syslog からの詳細情報
{detail}

"""

_SIMILAR_TMPL = """
## 過去の類似インシデント調査（参考）
{cases}

"""


def _summarize(incident: Incident) -> str:
    return "\n".join([
        f"- タイトル: {incident.title}",
        f"- 説明: {incident.description}",
        f"- 優先度: {incident.priority}",
        f"- ステータス: {incident.status}",
    ])


class InvestigationAgent:
    def __init__(
        self,
        llm: LLMClient,
        cache: QueryCache,
        rag: RAGStore,
        topology_client: TopologySyslogClient | None = None,
    ) -> None:
        self._llm = llm
        self._cache = cache
        self._rag = rag
        self._topology_client = topology_client

    def investigate(self, incident: Incident) -> str:
        """調査レポートを返す。キャッシュヒット時は LLM を呼び出さない。"""
        cached = self._cache.get(incident.fingerprint)
        if cached:
            _logger.debug("Cache hit: incident %s", incident.id)
            return cached

        similar = self._rag.search_similar(incident)
        similar_section = (
            _SIMILAR_TMPL.format(cases="\n---\n".join(similar)) if similar else ""
        )

        topology_report: str | None = None
        topology_detail: str | None = None
        if self._topology_client:
            topology_report = self._topology_client.get_report(incident)
            if topology_report is None:
                # topology-syslog 側の AI が無効の場合は生ログ等の詳細情報で代替
                topology_detail = self._topology_client.get_detail_text(incident)

        if topology_report is not None:
            _logger.info("LLM 呼び出し (行動指示プロンプト): incident %s", incident.id)
            prompt = _PROMPT_WITH_TOPO_REPORT.format(
                topology_report=topology_report,
                incident_summary=_summarize(incident),
                similar_section=similar_section,
            )
        else:
            _logger.info("LLM 呼び出し (汎用プロンプト): incident %s", incident.id)
            topology_section = (
                _TOPOLOGY_DETAIL_TMPL.format(detail=topology_detail) if topology_detail else ""
            )
            prompt = _PROMPT_GENERIC.format(
                incident_summary=_summarize(incident),
                topology_section=topology_section,
                similar_section=similar_section,
            )

        report = self._llm.ask(prompt)

        self._cache.set(incident.fingerprint, report)
        self._rag.add(incident, report)

        return report

    def investigate_with_recommendation(self, incident: Incident) -> InvestigationResult:
        """調査レポートとエスカレーション推奨を返す。"""
        report = self.investigate(incident)
        return InvestigationResult(report=report, escalate=_parse_escalation(report))

    def purge_cache(self) -> int:
        """TTL 切れのキャッシュ行を削除して削除件数を返す。"""
        return self._cache.purge_expired()
