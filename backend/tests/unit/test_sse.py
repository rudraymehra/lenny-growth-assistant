"""SSE relay guarantees, including the heartbeat-cancellation regression:
an engine event that takes LONGER than the heartbeat interval must still be
delivered (an earlier implementation cancelled the engine generator on every
heartbeat timeout, silently killing slow local-model generations)."""

import asyncio

from app.api.sse import encode_frame, sse_stream
from app.models.domain import DoneEvent, ErrorEvent, TokenEvent, Usage


async def collect(gen):
    return [frame async for frame in gen]


async def test_slow_event_survives_heartbeats():
    async def slow_engine():
        yield TokenEvent(text="fast")
        await asyncio.sleep(0.25)  # slower than the 0.05s heartbeat below
        yield TokenEvent(text=" slow")
        yield DoneEvent(usage=Usage(output_tokens=2))

    frames = await collect(sse_stream(slow_engine(), heartbeat_s=0.05))
    heartbeats = [f for f in frames if f.startswith(":")]
    tokens = [f for f in frames if f.startswith("event: token")]
    assert len(heartbeats) >= 2, "heartbeats should fire while the engine is busy"
    assert len(tokens) == 2, "the slow token must survive heartbeat timeouts"
    assert frames[-1].startswith("event: done")


async def test_terminal_frame_guaranteed_when_engine_ends_without_one():
    async def broken_engine():
        yield TokenEvent(text="partial")
        # ends without Done/Error — contract violation

    frames = await collect(sse_stream(broken_engine(), heartbeat_s=1))
    assert frames[-1].startswith("event: done")


async def test_engine_exception_becomes_error_frame():
    async def crashing_engine():
        yield TokenEvent(text="x")
        raise RuntimeError("boom")

    frames = await collect(sse_stream(crashing_engine(), heartbeat_s=1))
    assert frames[-1].startswith("event: error")
    assert "internal_error" in frames[-1]


def test_frame_encoding_shape():
    frame = encode_frame(ErrorEvent(code="model_timeout", message="slow", recoverable=True))
    assert frame.startswith("event: error\ndata: {")
    assert frame.endswith("\n\n")
    assert '"type"' not in frame  # type travels as the SSE event name, not payload
