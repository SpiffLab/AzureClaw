"""Tests for the research team service + orchestrator integration."""

from __future__ import annotations

import pytest

from azureclaw import GatewayHub
from azureclaw.adapters import InProcTestAdapter
from azureclaw.orchestrator import (
    Orchestrator,
    StubChatService,
    StubResearchService,
    StubTriageService,
    TriageDecision,
)
from azureclaw.orchestrator.intents import IntentChat, IntentResearch
from azureclaw.orchestrator.services import ResearchService

# ─── Protocol satisfaction ───────────────────────────────────────────────


@pytest.mark.local
def test_stub_research_service_satisfies_protocol() -> None:
    assert isinstance(StubResearchService("result"), ResearchService)


# ─── StubResearchService ────────────────────────────────────────────────


@pytest.mark.local
async def test_stub_returns_canned_result() -> None:
    svc = StubResearchService("summary of the page")
    result = await svc.research("summarize this", "https://example.com")
    assert result == "summary of the page"


@pytest.mark.local
async def test_stub_returns_canned_result_without_url() -> None:
    svc = StubResearchService("answer")
    result = await svc.research("what is the capital of France", None)
    assert result == "answer"


# ─── Orchestrator with research service ─────────────────────────────────


@pytest.mark.local
async def test_research_intent_with_service_produces_real_response() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(
        intents=[IntentResearch(query="summarize example.com", url="https://example.com")]
    )
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("unused"),
        hub=hub,
        research=StubResearchService("Research summary: example.com is a test domain."),
    )
    await orchestrator.start()
    await adapter.simulate_inbound("summarize example.com")

    assert len(adapter.received) == 1
    ev = adapter.received[0]
    assert ev.event_type == "completed"
    assert ev.payload["text"] == "Research summary: example.com is a test domain."
    assert "stub" not in ev.payload  # NOT a stub event


@pytest.mark.local
async def test_research_intent_without_service_still_produces_stub_event() -> None:
    """Backward compat: when research=None the stub event is emitted."""
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(intents=[IntentResearch(query="summarize this")])
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("unused"),
        hub=hub,
        # research=None (the default)
    )
    await orchestrator.start()
    await adapter.simulate_inbound("summarize example.com")

    assert len(adapter.received) == 1
    assert adapter.received[0].payload["stub"] is True
    assert "magentic-research-team" in adapter.received[0].payload["change_ref"]


@pytest.mark.local
async def test_mixed_chat_and_research_intents_both_produce_events() -> None:
    """Multi-intent: one chat + one research should produce two events."""
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(
        intents=[
            IntentChat(text="hello"),
            IntentResearch(query="summarize recipe"),
        ]
    )
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("Hi there!"),
        hub=hub,
        research=StubResearchService("Recipe summary here."),
    )
    await orchestrator.start()
    await adapter.simulate_inbound("hello and also summarize the recipe")

    assert len(adapter.received) == 2
    texts = {ev.payload.get("text") for ev in adapter.received}
    assert "Hi there!" in texts
    assert "Recipe summary here." in texts
