"""The documented fallback chain, exhaustively: requested provider × key
configured × ollama reachable."""

import pytest

from app.config import Settings


def settings(key: bool) -> Settings:
    return Settings(anthropic_api_key="sk-test" if key else "", database_url="postgresql://x/x")


@pytest.mark.parametrize("requested,key,ollama_ok,expected", [
    # auto: cloud when configured, else local, else nothing
    ("auto", True,  True,  "anthropic"),
    ("auto", True,  False, "anthropic"),
    ("auto", False, True,  "local"),
    ("auto", False, False, None),
    # explicit anthropic: key or bust (no silent downgrade to local)
    ("anthropic", True,  False, "anthropic"),
    ("anthropic", False, True,  None),
    # explicit local: ollama or bust (no silent upgrade to cloud)
    ("local", True,  False, None),
    ("local", False, True,  "local"),
    ("local", True,  True,  "local"),
])
def test_resolution_matrix(requested, key, ollama_ok, expected):
    assert settings(key).resolve_provider(requested, ollama_ok) == expected


def test_none_requested_uses_default_provider():
    s = settings(True)
    assert s.resolve_provider(None, ollama_ok=False) == "anthropic"
