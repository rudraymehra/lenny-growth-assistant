"""The engine seam. Both providers implement AgentEngine; the API layer is
engine-agnostic and just relays EngineEvents onto the SSE stream.

Contract:
- stream_reply yields zero or more Token/ToolUse/Citation/Artifact events and
  ALWAYS terminates with exactly one DoneEvent or ErrorEvent.
- Engines never write messages to the database; the route handler owns
  persistence so both engines get identical storage behaviour.
- Engines never pick their own provider: the session row carries the provider
  resolved at creation time (see router.py).
"""

from typing import AsyncIterator, Protocol

from app.models.domain import EngineEvent, EngineHealth, Message, Session


class AgentEngine(Protocol):
    name: str  # "anthropic" | "local"

    def stream_reply(
        self, session: Session, history: list[Message], user_content: str
    ) -> AsyncIterator[EngineEvent]:
        """Generate the assistant's reply as a stream of EngineEvents."""
        ...

    async def check(self) -> EngineHealth:
        """Cheap health probe for /health/ready and provider resolution."""
        ...
