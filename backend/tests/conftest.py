"""Shared fixtures.

Integration tests run against the compose Postgres using the dedicated
lenny_test database (created by scripts/pg-init), with a FakeEngine so no
model — cloud or local — is required. Unit tests need no fixtures beyond the
committed sample transcripts in tests/fixtures/.
"""

import os
from pathlib import Path
from typing import AsyncIterator

import asyncpg
import httpx
import pytest

from app.config import Settings
from app.db.pool import apply_schema
from app.db.repos import ArtifactRepo, KnowledgeRepo, MessageRepo, SessionRepo
from app.models.domain import (
    Citation, CitationEvent, DoneEvent, EngineEvent, EngineHealth, ErrorEvent,
    Message, Session, TokenEvent, Usage,
)

FIXTURES = Path(__file__).parent / "fixtures"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://lenny:lenny@postgres:5432/lenny_test"
)


# Function-scoped: asyncpg connections are bound to the event loop that
# created them, and pytest-asyncio gives each test its own loop.
@pytest.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=4)
    await apply_schema(pool)
    yield pool
    await pool.close()


@pytest.fixture
async def clean_db(pool: asyncpg.Pool) -> asyncpg.Pool:
    await pool.execute("TRUNCATE sessions, messages, artifacts, episodes, chunks, ingest_runs CASCADE")
    return pool


class FakeEngine:
    """Scripted engine honouring the AgentEngine contract."""

    def __init__(self, name: str = "local", events: list[EngineEvent] | None = None,
                 healthy: bool = True):
        self.name = name
        self.healthy = healthy
        self.events = events if events is not None else [
            TokenEvent(text="Grounded answer "),
            TokenEvent(text="with a citation [1]."),
            CitationEvent(citation=Citation(
                index=1, episode_slug="brian-chesky", episode_title="Ep",
                guest="Brian Chesky", ts_seconds=42,
                youtube_url="https://youtube.com/watch?v=x&t=42", quote="…",
            )),
            DoneEvent(usage=Usage(input_tokens=10, output_tokens=5, provider="local", model="fake")),
        ]
        self.calls: list[str] = []

    async def stream_reply(self, session: Session, history: list[Message], user_content: str):
        self.calls.append(user_content)
        for event in self.events:
            yield event

    async def check(self) -> EngineHealth:
        return EngineHealth(ok=self.healthy, detail="fake")


class FakeRouter:
    def __init__(self, engine: FakeEngine, provider: str = "local"):
        self._engine = engine
        self._provider = provider

    def engine_for(self, provider: str):
        return self._engine

    def model_for(self, provider: str, requested_model: str | None = None) -> str:
        return requested_model or "fake-model"

    async def resolve(self, requested: str | None):
        return self._provider if self._engine.healthy else None

    async def health(self) -> dict:
        h = await self._engine.check()
        return {"anthropic": h, "local": h}


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
async def client(clean_db: asyncpg.Pool, fake_engine: FakeEngine) -> AsyncIterator[httpx.AsyncClient]:
    """App wired exactly like production lifespan, but with the test pool and
    a scripted engine."""
    from app.main import create_app

    app = create_app(lifespan_ctx=None)
    app.state.settings = Settings(database_url=TEST_DATABASE_URL)
    app.state.pool = clean_db
    app.state.session_repo = SessionRepo(clean_db)
    app.state.message_repo = MessageRepo(clean_db)
    app.state.artifact_repo = ArtifactRepo(clean_db)
    app.state.knowledge_repo = KnowledgeRepo(clean_db)
    app.state.engine_router = FakeRouter(fake_engine)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


__all__ = ["FakeEngine", "FakeRouter", "ErrorEvent", "load_fixture"]
