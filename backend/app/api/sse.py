"""EngineEvent → Server-Sent-Events encoding.

Wire guarantees the frontend relies on:
- every stream ends with exactly one terminal frame (`done` or `error`),
  even if the engine crashes mid-generation;
- a comment heartbeat (`: hb`) at least every HEARTBEAT_S keeps proxies from
  buffering or closing slow local-model generations.

Implementation note: the engine generator is pumped by a background task into
a queue, and heartbeat timeouts apply to `queue.get()` only. Applying
`asyncio.wait_for` directly to the generator's `__anext__` would CANCEL the
generator on every heartbeat — cancelling exactly the long model call the
heartbeat exists to survive (found the hard way; regression-tested).
"""

import asyncio
import contextlib
from typing import AsyncIterator

from app.models.domain import DoneEvent, EngineEvent, ErrorEvent, Usage

HEARTBEAT_S = 15.0

_SENTINEL: object = object()


def encode_frame(event: EngineEvent) -> str:
    payload = event.model_dump_json(exclude={"type"})
    return f"event: {event.type}\ndata: {payload}\n\n"


async def sse_stream(
    events: AsyncIterator[EngineEvent], heartbeat_s: float | None = None
) -> AsyncIterator[str]:
    """Relay engine events as SSE frames with heartbeats and a guaranteed
    terminal frame."""
    heartbeat = heartbeat_s if heartbeat_s is not None else HEARTBEAT_S
    queue: asyncio.Queue = asyncio.Queue()

    async def pump() -> None:
        try:
            async for event in events:
                await queue.put(event)
        except Exception:  # noqa: BLE001 — engine broke its contract; report, don't hang
            await queue.put(ErrorEvent(
                code="internal_error",
                message="The response stream failed unexpectedly.",
                recoverable=False,
            ))
        finally:
            await queue.put(_SENTINEL)

    pump_task = asyncio.create_task(pump())
    terminal_sent = False
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except asyncio.TimeoutError:
                yield ": hb\n\n"
                continue
            if item is _SENTINEL:
                break
            if terminal_sent:
                # Invariant: exactly one terminal frame. Drop anything the
                # engine emits after done/error rather than send a second one.
                continue
            yield encode_frame(item)
            if isinstance(item, (DoneEvent, ErrorEvent)):
                terminal_sent = True
        if not terminal_sent:
            yield encode_frame(DoneEvent(usage=Usage()))
    finally:
        pump_task.cancel()
        with contextlib.suppress(BaseException):
            await pump_task  # let the engine/subprocess teardown settle
