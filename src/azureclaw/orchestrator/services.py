"""Service protocols for the orchestrator.

The orchestrator talks to ``TriageService`` and ``ChatService`` via
these thin Protocols. In production, the protocols are satisfied by
the MAF agent wrappers in ``triage.py`` and ``chat.py``. In tests,
they're satisfied by the stub implementations in ``stubs.py``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from azureclaw.orchestrator.intents import TriageDecision


@runtime_checkable
class TriageService(Protocol):
    """Classifies a user message into one or more intents."""

    async def classify(self, text: str) -> TriageDecision: ...


@runtime_checkable
class ChatService(Protocol):
    """Produces a conversational reply for a chat-intent message."""

    async def respond(self, text: str, session_id: str) -> str: ...
