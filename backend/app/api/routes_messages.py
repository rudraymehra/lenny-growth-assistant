"""The streaming reply endpoint — the seam where engines, persistence, and the
SSE wire meet. Engine-agnostic: it persists the user message, relays whatever
EngineEvents the session's engine emits, and persists the assistant message.
Note POST + SSE: browsers consume this with fetch()+ReadableStream, not
EventSource (which is GET-only).

Persistence is the subtle part. The assistant row is written when the
DoneEvent is *received* — before it is forwarded — and the write is shielded
from cancellation. That way a client that hits Stop or closes the tab (which
cancels this generator) can never lose a reply it already saw; a finally block
also persists whatever partial content streamed before an early disconnect.
Concurrent messages to one session are rejected with 409 to keep history and
the SDK resume handle consistent.
"""

import asyncio
import contextlib
from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.errors import ConflictError, NotFoundError
from app.api.sse import sse_stream
from app.logging import get_logger
from app.models.api import SendMessageRequest
from app.models.domain import (
    ArtifactEvent, CitationEvent, DoneEvent, EngineEvent, ErrorEvent, TokenEvent, Usage,
)

router = APIRouter()
log = get_logger(__name__)

_TITLE_MAX = 60

# One in-flight reply per session. asyncio.Lock is process-local, which matches
# the single-backend deployment; a multi-replica deployment would swap this for
# a Postgres advisory lock (documented in architecture.md).
_session_locks: dict[UUID, asyncio.Lock] = {}


def _lock_for(session_id: UUID) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: UUID, req: SendMessageRequest, request: Request
) -> StreamingResponse:
    state = request.app.state
    session = await state.session_repo.get(session_id)
    if not session:
        raise NotFoundError("Session not found.")

    lock = _lock_for(session_id)
    if lock.locked():
        raise ConflictError("This conversation already has a reply in progress.")

    history = await state.message_repo.list_for_session(session_id)
    await state.message_repo.add(session_id, "user", req.content)
    # First user message names the session (trimmed), like every chat product.
    title = req.content[:_TITLE_MAX] if not history else None
    await state.session_repo.touch(session_id, title=title)

    engine = state.engine_router.engine_for(session.provider)

    async def relay() -> AsyncIterator[EngineEvent]:
        """Forward events while accumulating what persistence needs; persist the
        assistant row before forwarding the terminal frame, shielded so a
        client disconnect can't lose it."""
        content_parts: list[str] = []
        citations, artifact_id, usage = [], None, Usage()
        persisted = False

        async def persist() -> None:
            nonlocal persisted
            if persisted:
                return
            persisted = True
            await state.message_repo.add(
                session_id, "assistant", "".join(content_parts).strip(),
                citations=citations, artifact_id=artifact_id, usage=usage,
            )
            await state.session_repo.touch(session_id)

        await lock.acquire()
        try:
            async for event in engine.stream_reply(session, history, req.content):
                if isinstance(event, TokenEvent):
                    content_parts.append(event.text)
                elif isinstance(event, CitationEvent):
                    citations.append(event.citation)
                elif isinstance(event, ArtifactEvent):
                    artifact_id = event.artifact_id
                elif isinstance(event, DoneEvent):
                    usage = event.usage
                    try:
                        await asyncio.shield(persist())
                    except Exception as exc:  # noqa: BLE001
                        log.error("persist.failed", detail=str(exc))
                        yield ErrorEvent(
                            code="db_unavailable",
                            message="The reply was generated but could not be saved.",
                            recoverable=False,
                        )
                        return
                    yield event
                    return
                elif isinstance(event, ErrorEvent):
                    if content_parts:
                        with contextlib.suppress(Exception):
                            await asyncio.shield(persist())
                    yield event
                    return
                yield event
        finally:
            # Early disconnect / cancellation mid-stream: keep what we have.
            if content_parts and not persisted:
                with contextlib.suppress(Exception):
                    await asyncio.shield(persist())
            lock.release()

    return StreamingResponse(
        sse_stream(relay()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
