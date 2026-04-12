"""AzureClaw orchestrator — intent-based message routing.

Re-exports the public surface: the ``Orchestrator`` class, the
``TriageDecision`` discriminated union and its variant types, and
the service Protocols + stubs for dependency injection.
"""

from azureclaw.orchestrator.intents import (
    Intent,
    IntentChat,
    IntentOnPrem,
    IntentResearch,
    IntentSchedule,
    TriageDecision,
)
from azureclaw.orchestrator.orchestrator import Orchestrator
from azureclaw.orchestrator.services import ChatService, TriageService
from azureclaw.orchestrator.stubs import StubChatService, StubTriageService

__all__ = [
    "ChatService",
    "Intent",
    "IntentChat",
    "IntentOnPrem",
    "IntentResearch",
    "IntentSchedule",
    "Orchestrator",
    "StubChatService",
    "StubTriageService",
    "TriageDecision",
    "TriageService",
]
