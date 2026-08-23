"""Non-secret runtime configuration for the UI: which providers are usable,
which models are active, and knowledge-base freshness (powers the provider
badge and the KB info popover). Never exposes keys or full URLs."""

from urllib.parse import urlparse

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/config")
async def get_config(request: Request) -> dict:
    state = request.app.state
    settings = state.settings
    health = await state.engine_router.health()
    kb = await state.knowledge_repo.stats()
    return {
        "default_provider": settings.default_provider,
        "providers": {
            "anthropic": {
                "configured": health["anthropic"].ok,
                "model": settings.anthropic_model,
            },
            "local": {
                "reachable": health["local"].ok,
                "detail": health["local"].detail,
                "model": settings.ollama_model,
                "host": urlparse(settings.ollama_base_url).hostname,
            },
        },
        "embedding_model": settings.embedding_model,
        "kb": kb,
    }
