"""Health endpoints.

/health        — liveness: process is up, no dependency checks.
/health/ready  — readiness: DB round-trip (hard requirement) + provider
                 availability (informational). The Anthropic check is key
                 presence only and the Ollama check is a cached /api/tags —
                 readiness never spends API credit or loads a model.
"""

import time

from fastapi import APIRouter, Request, Response

router = APIRouter()

_OLLAMA_CACHE_S = 10
_cache: dict = {"ts": 0.0, "result": None}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request, response: Response) -> dict:
    from app.db.pool import check_db

    state = request.app.state
    db_ok, db_latency = await check_db(state.pool)

    now = time.monotonic()
    if _cache["result"] is None or now - _cache["ts"] > _OLLAMA_CACHE_S:
        _cache["result"] = await state.engine_router.engine_for("local").check()
        _cache["ts"] = now
    ollama = _cache["result"]

    anthropic = await state.engine_router.engine_for("anthropic").check()

    if not db_ok:
        response.status_code = 503
    return {
        "status": "ok" if db_ok else "degraded",
        "checks": {
            "db": {"ok": db_ok, "latency_ms": round(db_latency, 1)},
            "ollama": {"ok": ollama.ok, "detail": ollama.detail},
            "anthropic": {"configured": anthropic.ok},
        },
    }
