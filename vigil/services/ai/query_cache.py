"""インシデント fingerprint ベースの AI 調査キャッシュ（SQLite）。

同一 fingerprint（source + title の SHA-256）のインシデントが再発した場合、
LLM への再問い合わせをスキップして即返却する。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool


class _Base(DeclarativeBase):
    pass


class _CacheRow(_Base):
    __tablename__ = "vigil_ai_cache"
    fingerprint = Column(String,   primary_key=True)
    report      = Column(Text,     nullable=False)
    created_at  = Column(DateTime, nullable=False)


def _make_engine(database_url: str):
    if "sqlite" in database_url:
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool
        return create_engine(database_url, **kwargs)
    return create_engine(database_url)


class QueryCache:
    def __init__(self, database_url: str, ttl_days: int = 7) -> None:
        self._engine = _make_engine(database_url)
        _Base.metadata.create_all(self._engine)
        self._ttl = timedelta(days=ttl_days)

    def get(self, fingerprint: str | None) -> str | None:
        if not fingerprint:
            return None
        cutoff = (datetime.now(tz=timezone.utc) - self._ttl).replace(tzinfo=None)
        with Session(self._engine) as session:
            row = session.get(_CacheRow, fingerprint)
            if row and row.created_at >= cutoff:
                return row.report
        return None

    def set(self, fingerprint: str | None, report: str) -> None:
        if not fingerprint:
            return
        with Session(self._engine) as session:
            session.merge(_CacheRow(
                fingerprint=fingerprint,
                report=report,
                created_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            ))
            session.commit()

    def purge_expired(self) -> int:
        """TTL 切れのキャッシュ行を削除して削除件数を返す。"""
        cutoff = (datetime.now(tz=timezone.utc) - self._ttl).replace(tzinfo=None)
        with Session(self._engine) as session:
            rows = session.scalars(select(_CacheRow).where(_CacheRow.created_at < cutoff)).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
        return count
