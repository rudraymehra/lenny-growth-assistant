"""Session lifecycle: creation (where provider resolution happens, once) and
listing/reading."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.errors import NotFoundError, ProviderUnavailableError
from app.models.api import (
    CreateSessionRequest, MessageListResponse, MessageResponse,
    SessionListResponse, SessionResponse,
)

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest, request: Request) -> SessionResponse:
    state = request.app.state
    provider = await state.engine_router.resolve(req.provider)
    if provider is None:
        raise ProviderUnavailableError(
            "No usable model provider. Set ANTHROPIC_API_KEY in .env for the cloud model, "
            "or start Ollama (brew services start ollama && ollama pull "
            f"{state.settings.ollama_model}) for the local model."
        )
    model = state.engine_router.model_for(provider, req.model)
    session = await state.session_repo.create(
        title=req.title or "New conversation", provider=provider, model=model
    )
    return SessionResponse(
        id=session.id, title=session.title, provider=session.provider,
        model=session.model, created_at=session.created_at, updated_at=session.updated_at,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request) -> SessionListResponse:
    pairs = await request.app.state.session_repo.list_with_counts()
    return SessionListResponse(sessions=[
        SessionResponse(
            id=s.id, title=s.title, provider=s.provider, model=s.model,
            created_at=s.created_at, updated_at=s.updated_at, message_count=count,
        )
        for s, count in pairs
    ])


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_messages(session_id: UUID, request: Request) -> MessageListResponse:
    state = request.app.state
    if not await state.session_repo.get(session_id):
        raise NotFoundError("Session not found.")
    messages = await state.message_repo.list_for_session(session_id)
    return MessageListResponse(messages=[
        MessageResponse(
            id=m.id, role=m.role, content=m.content, citations=m.citations,
            artifact_id=m.artifact_id, usage=m.usage, created_at=m.created_at,
        )
        for m in messages
    ])
