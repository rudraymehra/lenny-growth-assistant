"""Request/response contracts for /api/v1. Kept separate from domain models
so the wire format can evolve without touching engine or persistence code."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.domain import Citation, Usage


class CreateSessionRequest(BaseModel):
    provider: Literal["auto", "anthropic", "local"] | None = None
    model: str | None = None
    title: str | None = Field(default=None, max_length=200)


class SessionResponse(BaseModel):
    id: UUID
    title: str
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[Citation]
    artifact_id: UUID | None
    usage: Usage | None
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ArtifactResponse(BaseModel):
    id: UUID
    session_id: UUID
    kind: str
    title: str
    content: str  # sanitized by default; raw only via ?raw=true
    created_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
