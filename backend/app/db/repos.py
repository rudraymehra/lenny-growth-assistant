"""Persistence for sessions, messages, and artifacts. Plain SQL via asyncpg —
no ORM; every query is visible and explainable."""

import json
from uuid import UUID

import asyncpg

from app.models.domain import Artifact, Citation, Message, Session, Usage


def _session_from_row(row: asyncpg.Record) -> Session:
    return Session(
        id=row["id"],
        title=row["title"],
        provider=row["provider"],
        model=row["model"],
        sdk_session_id=row["sdk_session_id"],
        user_metadata=json.loads(row["user_metadata"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message_from_row(row: asyncpg.Record) -> Message:
    usage_raw = json.loads(row["usage"])
    return Message(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        citations=[Citation(**c) for c in json.loads(row["citations"])],
        artifact_id=row["artifact_id"],
        usage=Usage(**usage_raw) if usage_raw else None,
        created_at=row["created_at"],
    )


class SessionRepo:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(
        self, title: str, provider: str, model: str, user_metadata: dict | None = None
    ) -> Session:
        row = await self._pool.fetchrow(
            """INSERT INTO sessions (title, provider, model, user_metadata)
               VALUES ($1, $2, $3, $4) RETURNING *""",
            title, provider, model, json.dumps(user_metadata or {}),
        )
        return _session_from_row(row)

    async def get(self, session_id: UUID) -> Session | None:
        row = await self._pool.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
        return _session_from_row(row) if row else None

    async def list_with_counts(self) -> list[tuple[Session, int]]:
        rows = await self._pool.fetch(
            """SELECT s.*, count(m.id) AS message_count
               FROM sessions s LEFT JOIN messages m ON m.session_id = s.id
               GROUP BY s.id ORDER BY s.updated_at DESC"""
        )
        return [(_session_from_row(r), r["message_count"]) for r in rows]

    async def touch(self, session_id: UUID, title: str | None = None) -> None:
        if title:
            await self._pool.execute(
                "UPDATE sessions SET updated_at = now(), title = $2 WHERE id = $1",
                session_id, title,
            )
        else:
            await self._pool.execute(
                "UPDATE sessions SET updated_at = now() WHERE id = $1", session_id
            )

    async def set_sdk_session_id(self, session_id: UUID, sdk_session_id: str) -> None:
        await self._pool.execute(
            "UPDATE sessions SET sdk_session_id = $2 WHERE id = $1", session_id, sdk_session_id
        )


class MessageRepo:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def add(
        self,
        session_id: UUID,
        role: str,
        content: str,
        citations: list[Citation] | None = None,
        artifact_id: UUID | None = None,
        usage: Usage | None = None,
    ) -> Message:
        row = await self._pool.fetchrow(
            """INSERT INTO messages (session_id, role, content, citations, artifact_id, usage)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            session_id, role, content,
            json.dumps([c.model_dump() for c in (citations or [])]),
            artifact_id,
            json.dumps(usage.model_dump() if usage else {}),
        )
        return _message_from_row(row)

    async def list_for_session(self, session_id: UUID) -> list[Message]:
        rows = await self._pool.fetch(
            "SELECT * FROM messages WHERE session_id = $1 ORDER BY created_at", session_id
        )
        return [_message_from_row(r) for r in rows]


class ArtifactRepo:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(
        self, session_id: UUID, kind: str, title: str, content: str, sanitized_content: str
    ) -> Artifact:
        row = await self._pool.fetchrow(
            """INSERT INTO artifacts (session_id, kind, title, content, sanitized_content)
               VALUES ($1, $2, $3, $4, $5) RETURNING *""",
            session_id, kind, title, content, sanitized_content,
        )
        return Artifact(**dict(row))

    async def get(self, artifact_id: UUID) -> Artifact | None:
        row = await self._pool.fetchrow("SELECT * FROM artifacts WHERE id = $1", artifact_id)
        return Artifact(**dict(row)) if row else None


class KnowledgeRepo:
    """Read-side stats for /config; write-side lives in ingest/cli.py."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def stats(self) -> dict:
        row = await self._pool.fetchrow(
            """SELECT (SELECT count(*) FROM episodes) AS episodes,
                      (SELECT count(*) FROM chunks) AS chunks"""
        )
        last = await self._pool.fetchrow(
            "SELECT status, finished_at, chunks_written FROM ingest_runs ORDER BY started_at DESC LIMIT 1"
        )
        return {
            "episodes": row["episodes"],
            "chunks": row["chunks"],
            "last_ingest": dict(last) if last else None,
        }
