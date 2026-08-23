"""Domain objects shared across the API, engines, and persistence layers,
including the EngineEvent union — the wire-agnostic streaming protocol every
engine speaks (see engines/base.py for the contract)."""

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A grounded reference to a retrieved transcript chunk. Built by the
    backend from actually-retrieved chunks — never authored by the model."""

    index: int
    episode_slug: str
    episode_title: str
    guest: str
    ts_seconds: int
    youtube_url: str | None = None  # deep link including &t={ts_seconds}
    quote: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider: str = ""
    model: str = ""


class Session(BaseModel):
    id: UUID
    title: str
    provider: Literal["anthropic", "local"]
    model: str
    sdk_session_id: str | None = None
    user_metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    id: UUID
    session_id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = Field(default_factory=list)
    artifact_id: UUID | None = None
    usage: Usage | None = None
    created_at: datetime


class Artifact(BaseModel):
    id: UUID
    session_id: UUID
    kind: Literal["markdown", "html"]
    title: str
    content: str
    sanitized_content: str
    created_at: datetime


class RetrievedChunk(BaseModel):
    """A retrieval hit with everything needed to build a Citation."""

    chunk_id: int
    episode_slug: str
    episode_title: str
    guest: str
    youtube_url: str | None
    speaker: str | None
    start_ts: int
    end_ts: int
    content: str
    score: float


# ── EngineEvent: the streaming protocol both engines emit ───────────────────

class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ToolUseEvent(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    tool: str
    summary: str


class CitationEvent(BaseModel):
    type: Literal["citation"] = "citation"
    citation: Citation


class ArtifactEvent(BaseModel):
    type: Literal["artifact"] = "artifact"
    artifact_id: UUID
    kind: Literal["markdown", "html"]
    title: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    usage: Usage


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    recoverable: bool = False


EngineEvent = Annotated[
    Union[TokenEvent, ToolUseEvent, CitationEvent, ArtifactEvent, DoneEvent, ErrorEvent],
    Field(discriminator="type"),
]


class EngineHealth(BaseModel):
    ok: bool
    detail: str = ""
