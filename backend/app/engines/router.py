"""Provider resolution and engine lookup.

Resolution happens exactly once, at session creation (see Settings.resolve_provider):
  - explicit "anthropic" → requires a configured key
  - explicit "local"     → requires reachable Ollama with the model pulled
  - "auto" (default)     → anthropic if configured, else local, else nothing
The resolved provider is stamped on the session row and shown in the UI badge.
There is NO silent mid-conversation fallback: if a session's provider fails at
reply time, the stream carries a typed error event and the user chooses what
to do (retry, or start a new session on the other provider). Grounding and
cost transparency beat availability theater.
"""

import asyncpg

from app.config import Provider, Settings
from app.engines.base import AgentEngine
from app.engines.claude_engine import ClaudeAgentEngine
from app.engines.local_engine import LocalRagEngine


class EngineRouter:
    def __init__(self, settings: Settings, pool: asyncpg.Pool):
        self._settings = settings
        self._engines: dict[str, AgentEngine] = {
            "anthropic": ClaudeAgentEngine(settings, pool),
            "local": LocalRagEngine(settings, pool),
        }

    def engine_for(self, provider: str) -> AgentEngine:
        return self._engines[provider]

    def model_for(self, provider: Provider, requested_model: str | None = None) -> str:
        if requested_model:
            return requested_model
        return (
            self._settings.anthropic_model if provider == "anthropic"
            else self._settings.ollama_model
        )

    async def resolve(self, requested: str | None) -> Provider | None:
        """Apply the documented fallback chain. Ollama reachability is only
        probed when the decision needs it (never spends an API call)."""
        choice = requested or self._settings.default_provider
        needs_ollama_check = choice in ("local", "auto") and not (
            choice == "auto" and self._settings.anthropic_configured
        )
        ollama_ok = False
        if needs_ollama_check:
            ollama_ok = (await self._engines["local"].check()).ok
        return self._settings.resolve_provider(requested, ollama_ok)

    async def health(self) -> dict:
        return {name: await engine.check() for name, engine in self._engines.items()}
