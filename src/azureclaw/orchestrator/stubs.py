"""Stub service implementations for tests.

Three-line classes that satisfy the ``TriageService`` and ``ChatService``
protocols without importing MAF or constructing any SDK object.
"""

from __future__ import annotations

from azureclaw.orchestrator.intents import TriageDecision


class StubTriageService:
    """Returns a canned ``TriageDecision`` for every input."""

    def __init__(self, decision: TriageDecision) -> None:
        self._decision = decision

    async def classify(self, text: str) -> TriageDecision:
        return self._decision


class StubChatService:
    """Returns a canned reply for every input."""

    def __init__(self, reply: str = "stub-reply") -> None:
        self._reply = reply

    async def respond(self, text: str, session_id: str) -> str:
        return self._reply


class StubResearchService:
    """Returns a canned research result for every input."""

    def __init__(self, result: str = "stub-research-result") -> None:
        self._result = result

    async def research(self, query: str, url: str | None) -> str:
        return self._result
