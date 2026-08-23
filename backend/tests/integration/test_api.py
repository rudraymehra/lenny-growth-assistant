"""API contract + persistence round-trips with a scripted engine.
Covers: session CRUD, the SSE wire (frame ordering, guaranteed terminal
frame), error envelopes, health, and artifact retrieval."""

import json

import httpx
import pytest

from app.models.domain import ErrorEvent, TokenEvent
from tests.conftest import FakeEngine


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    frames = []
    for block in raw.split("\n\n"):
        lines = [l for l in block.strip().splitlines() if l and not l.startswith(":")]
        if not lines:
            continue
        event = next(l.removeprefix("event: ") for l in lines if l.startswith("event: "))
        data = next(l.removeprefix("data: ") for l in lines if l.startswith("data: "))
        frames.append((event, json.loads(data)))
    return frames


async def test_session_lifecycle(client: httpx.AsyncClient):
    resp = await client.post("/api/v1/sessions", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["provider"] == "local"
    assert body["model"] == "fake-model"

    listed = (await client.get("/api/v1/sessions")).json()["sessions"]
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]
    assert listed[0]["message_count"] == 0


async def test_validation_error_envelope(client: httpx.AsyncClient):
    resp = await client.post("/api/v1/sessions", json={"provider": "banana"})
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert err["request_id"]


async def test_not_found_envelope(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000/messages")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_message_stream_and_persistence(client: httpx.AsyncClient):
    session_id = (await client.post("/api/v1/sessions", json={})).json()["id"]
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "What is founder mode?"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(resp.text)

    kinds = [k for k, _ in frames]
    assert kinds[0] == "token"
    assert kinds[-1] == "done"          # guaranteed terminal frame
    assert "citation" in kinds
    citation = next(d for k, d in frames if k == "citation")["citation"]
    assert citation["youtube_url"].endswith("t=42")

    # persistence round-trip
    messages = (await client.get(f"/api/v1/sessions/{session_id}/messages")).json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Grounded answer with a citation [1]."
    assert messages[1]["citations"][0]["episode_slug"] == "brian-chesky"
    assert messages[1]["usage"]["output_tokens"] == 5

    # first message titles the session
    sessions = (await client.get("/api/v1/sessions")).json()["sessions"]
    assert sessions[0]["title"] == "What is founder mode?"
    assert sessions[0]["message_count"] == 2


async def test_empty_message_rejected(client: httpx.AsyncClient):
    session_id = (await client.post("/api/v1/sessions", json={})).json()["id"]
    resp = await client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": ""})
    assert resp.status_code == 422


async def test_engine_error_yields_error_frame_and_no_assistant_row(
    clean_db, fake_engine: FakeEngine
):
    fake_engine.events = [
        ErrorEvent(code="ollama_unreachable", message="down", recoverable=True)
    ]
    from tests.conftest import FakeRouter
    from app.main import create_app
    from app.config import Settings
    from app.db.repos import ArtifactRepo, KnowledgeRepo, MessageRepo, SessionRepo
    from tests.conftest import TEST_DATABASE_URL

    app = create_app(lifespan_ctx=None)
    app.state.settings = Settings(database_url=TEST_DATABASE_URL)
    app.state.pool = clean_db
    app.state.session_repo = SessionRepo(clean_db)
    app.state.message_repo = MessageRepo(clean_db)
    app.state.artifact_repo = ArtifactRepo(clean_db)
    app.state.knowledge_repo = KnowledgeRepo(clean_db)
    app.state.engine_router = FakeRouter(fake_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = (await client.post("/api/v1/sessions", json={})).json()["id"]
        resp = await client.post(
            f"/api/v1/sessions/{session_id}/messages", json={"content": "hi"}
        )
        frames = parse_sse(resp.text)
        assert frames[-1][0] == "error"
        assert frames[-1][1]["code"] == "ollama_unreachable"
        messages = (await client.get(f"/api/v1/sessions/{session_id}/messages")).json()["messages"]
        # the user message persists; no half-empty assistant message is stored
        assert [m["role"] for m in messages] == ["user"]


async def test_provider_unavailable_maps_to_503(client: httpx.AsyncClient, fake_engine: FakeEngine):
    fake_engine.healthy = False
    resp = await client.post("/api/v1/sessions", json={"provider": "local"})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "provider_unavailable"


async def test_artifact_roundtrip(client: httpx.AsyncClient, clean_db):
    from app.artifacts.store import save_artifact
    from app.db.repos import ArtifactRepo, SessionRepo

    session = await SessionRepo(clean_db).create("t", "local", "fake")
    artifact = await save_artifact(
        ArtifactRepo(clean_db), session.id, "html", "Hostile",
        '<h1>ok</h1><script>alert(1)</script>',
    )
    sanitized = (await client.get(f"/api/v1/artifacts/{artifact.id}")).json()
    assert "<script" not in sanitized["content"]
    assert "<h1>ok</h1>" in sanitized["content"]
    raw = (await client.get(f"/api/v1/artifacts/{artifact.id}?raw=true")).json()
    assert "<script" in raw["content"]  # audit view keeps the original


async def test_health_liveness(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_config_reports_kb_stats(client: httpx.AsyncClient):
    body = (await client.get("/api/v1/config")).json()
    assert body["kb"]["episodes"] == 0
    assert "providers" in body
