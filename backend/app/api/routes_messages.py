"""The streaming reply endpoint — the seam where engines, persistence, and the
SSE wire meet. Engine-agnostic: it persists the user message, relays whatever
EngineEvents the session's engine emits, and persists the assistant message
when the stream completes. Note POST + SSE: browsers consume this with
fetch()+ReadableStream, not EventSource (which is GET-only)."""

from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.errors import NotFoundError
from app.api.sse import sse_stream
from app.models.api import SendMessageRequest
from app.models.domain import (
    ArtifactEvent, CitationEvent, DoneEvent, EngineEvent, ErrorEvent, TokenEvent,
)

router = APIRouter()

_TITLE_MAX = 60


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: UUID, req: SendMessageRequest, request: Request
) -> StreamingResponse:
    state = request.app.state
    session = await state.session_repo.get(session_id)
    if not session:
        raise NotFoundError("Session not found.")

    history = await state.message_repo.list_for_session(session_id)
    await state.message_repo.add(session_id, "user", req.content)
    # First user message names the session (trimmed), like every chat product.
    title = req.content[:_TITLE_MAX] if not history else None
    await state.session_repo.touch(session_id, title=title)

    engine = state.engine_router.engine_for(session.provider)

    async def relay() -> AsyncIterator[EngineEvent]:
        """Pass events through while accumulating what persistence needs."""
        content_parts: list[str] = []
        citations, artifact_id, usage = [], None, None
        async for event in engine.stream_reply(session, history, req.content):
            if isinstance(event, TokenEvent):
                content_parts.append(event.text)
            elif isinstance(event, CitationEvent):
                citations.append(event.citation)
            elif isinstance(event, ArtifactEvent):
                artifact_id = event.artifact_id
            elif isinstance(event, DoneEvent):
                usage = event.usage
            elif isinstance(event, ErrorEvent) and not content_parts:
                # Nothing generated: surface the error, persist nothing.
                yield event
                return
            yield event
        message = await state.message_repo.add(
            session_id, "assistant", "".join(content_parts).strip(),
            citations=citations, artifact_id=artifact_id, usage=usage,
        )
        await state.session_repo.touch(session_id)
        # done frame already forwarded; message_id travels on a final comment-
        # free frame only if needed — clients reload messages on completion.
        _ = message

    return StreamingResponse(
        sse_stream(relay()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
