"""vigil インシデント調査履歴 RAG ストア（ChromaDB ベース）。

調査レポートをインシデント情報とセットで保存し、
類似インシデントの過去調査をコンテキストとして活用する。
"""
from __future__ import annotations

import logging

from vigil.models import Incident

_logger = logging.getLogger(__name__)
_COLLECTION = "vigil_investigations"


def _to_query_text(incident: Incident) -> str:
    """類似検索クエリ用テキスト（レポートなし）。"""
    return "\n".join([
        f"Title: {incident.title}",
        f"Description: {incident.description}",
        f"Priority: {incident.priority}",
    ])


def _to_document(incident: Incident, report: str) -> str:
    """保存用テキスト（調査レポート込み）。"""
    return "\n".join([
        f"Title: {incident.title}",
        f"Description: {incident.description}",
        f"Priority: {incident.priority}",
        "",
        "--- 調査レポート ---",
        report,
    ])


class RAGStore:
    def __init__(self, persist_path: str) -> None:
        import chromadb  # lazy import — optional dep (pip install vigil[ai])
        client = chromadb.PersistentClient(path=persist_path)
        self._col = client.get_or_create_collection(name=_COLLECTION)

    def add(self, incident: Incident, report: str) -> None:
        """インシデントと調査レポートをベクターストアに追加（同 ID は上書き）。"""
        self._col.upsert(
            ids=[incident.id],
            documents=[_to_document(incident, report)],
            metadatas=[{
                "title": incident.title[:200],
                "priority": str(incident.priority),
                "created_at": incident.created_at.isoformat(),
            }],
        )

    def search_similar(self, incident: Incident, n: int = 3) -> list[str]:
        """意味的に類似した過去調査レポートを最大 n 件返す。自身は除外。"""
        total = self._col.count()
        if total == 0:
            return []
        try:
            results = self._col.query(
                query_texts=[_to_query_text(incident)],
                n_results=min(n + 1, total),
            )
            docs = results["documents"][0] if results["documents"] else []
            ids  = results["ids"][0]       if results["ids"]       else []
            return [d for d, i in zip(docs, ids) if i != incident.id][:n]
        except Exception as exc:
            _logger.warning("RAG search failed: %s", exc)
            return []
