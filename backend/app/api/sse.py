"""EngineEvent → Server-Sent-Events encoding.

Wire guarantees the frontend relies on:
- every stream ends with exactly one terminal frame (`done` or `error`),
  even if the engine crashes mid-generation;
- a comment heartbeat (`: hb`) at least every HEARTBEAT_S keeps proxies from
  buffering or closing slow local-model generations.
"""

import asyncio
from typing import AsyncIterator

from app.models.domain import DoneEvent, EngineEvent, ErrorEvent, Usage

HEARTBEAT_S = 15


def encode_frame(event: EngineEvent) -> str:
    payload = event.model_dump_json(exclude={"type"})
    return f"event: {event.type}\ndata: {payload}\n\n"


async def sse_stream(events: AsyncIterator[EngineEvent]) -> AsyncIterator[str]:
    """Relay engine events as SSE frames with heartbeats and a guaranteed
    terminal frame."""
    terminal_sent = False
    iterator = events.__aiter__()
    try:
        while True:
            try:
                event = await asyncio.wait_for(iterator.__anext__(), timeout=HEARTBEAT_S)
            except asyncio.TimeoutError:
                yield ": hb\n\n"
                continue
            except StopAsyncIteration:
                break
            if isinstance(event, (DoneEvent, ErrorEvent)):
                terminal_sent = True
            yield encode_frame(event)
    except Exception:  # noqa: BLE001 — engine broke its contract; still terminate the wire
        yield encode_frame(ErrorEvent(
            code="internal_error", message="The response stream failed unexpectedly.",
            recoverable=False,
        ))
        terminal_sent = True
    if not terminal_sent:
        yield encode_frame(DoneEvent(usage=Usage()))
