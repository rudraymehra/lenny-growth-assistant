"""Application settings. The single module that reads the environment —
everything else receives typed values from here."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["anthropic", "local"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://lenny:lenny@postgres:5432/lenny"

    default_provider: Literal["auto", "anthropic", "local"] = "auto"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:4b"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    transcripts_dir: str = "/data/transcripts"
    retrieval_top_k: int = 8

    model_timeout_s: float = 120.0
    max_concurrent_agent_sessions: int = 2
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    experimental_sdk_via_ollama: bool = False

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    def resolve_provider(self, requested: str | None, ollama_ok: bool) -> Provider | None:
        """Resolve a session's provider exactly once, at session creation.

        Returns None when nothing usable is available (caller maps this to a
        structured 503). A session is stamped with the resolved provider and
        never switches silently afterwards.
        """
        choice = requested or self.default_provider
        if choice == "anthropic":
            return "anthropic" if self.anthropic_configured else None
        if choice == "local":
            return "local" if ollama_ok else None
        # auto: prefer cloud when configured, else local when reachable
        if self.anthropic_configured:
            return "anthropic"
        if ollama_ok:
            return "local"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
