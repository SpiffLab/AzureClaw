"""Tests for the Orchestrator dispatch loop."""

from __future__ import annotations

import pytest

from azureclaw import GatewayHub
from azureclaw.adapters import InProcTestAdapter
from azureclaw.orchestrator import (
    Orchestrator,
    StubChatService,
    StubTriageService,
    TriageDecision,
)
from azureclaw.orchestrator.intents import (
    IntentChat,
    IntentOnPrem,
    IntentResearch,
    IntentSchedule,
)
from azureclaw.orchestrator.services import ChatService, TriageService

# ─── Protocol satisfaction ───────────────────────────────────────────────


@pytest.mark.local
def test_stubs_satisfy_protocols() -> None:
    decision = TriageDecision(intents=[IntentChat(text="hi")])
    assert isinstance(StubTriageService(decision), TriageService)
    assert isinstance(StubChatService("reply"), ChatService)


# ─── Single-intent dispatch ─────────────────────────────────────────────


@pytest.mark.local
async def test_chat_intent_produces_completed_event() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(intents=[IntentChat(text="hello")])
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("echo: hello"),
        hub=hub,
    )
    await orchestrator.start()
    await adapter.simulate_inbound("hello")

    assert len(adapter.received) == 1
    assert adapter.received[0].event_type == "completed"
    assert adapter.received[0].payload["text"] == "echo: hello"


@pytest.mark.local
async def test_schedule_intent_produces_stub_event() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(intents=[IntentSchedule(description="remind me", when="5pm")])
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("unused"),
        hub=hub,
    )
    await orchestrator.start()
    await adapter.simulate_inbound("remind me at 5pm")

    assert len(adapter.received) == 1
    assert adapter.received[0].payload["stub"] is True
    assert "approval-loop-servicebus" in adapter.received[0].payload["change_ref"]


@pytest.mark.local
async def test_research_intent_produces_stub_event() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(intents=[IntentResearch(query="summarize this")])
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("unused"),
        hub=hub,
    )
    await orchestrator.start()
    await adapter.simulate_inbound("summarize example.com")

    assert len(adapter.received) == 1
    assert adapter.received[0].payload["stub"] is True
    assert "magentic-research-team" in adapter.received[0].payload["change_ref"]


@pytest.mark.local
async def test_onprem_intent_produces_stub_event() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(intents=[IntentOnPrem(site_id="home", action="list shares")])
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("unused"),
        hub=hub,
    )
    await orchestrator.start()
    await adapter.simulate_inbound("on site:home list shares")

    assert len(adapter.received) == 1
    assert adapter.received[0].payload["stub"] is True
    assert "onprem-peer-a2a" in adapter.received[0].payload["change_ref"]


# ─── Multi-intent fan-out ────────────────────────────────────────────────


@pytest.mark.local
async def test_multi_intent_produces_multiple_events() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(
        intents=[
            IntentSchedule(description="reminder", when="6pm"),
            IntentResearch(query="summarize recipe", url="https://example.com"),
        ]
    )
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("unused"),
        hub=hub,
    )
    await orchestrator.start()
    await adapter.simulate_inbound("remind me and also summarize")

    assert len(adapter.received) == 2
    change_refs = {ev.payload["change_ref"] for ev in adapter.received}
    assert "approval-loop-servicebus" in change_refs
    assert "magentic-research-team" in change_refs


# ─── Full round-trip ─────────────────────────────────────────────────────


@pytest.mark.local
async def test_full_round_trip_inproc_to_orchestrator_and_back() -> None:
    """The first REAL round-trip: InProcTestAdapter → hub → orchestrator
    (triage → chat) → hub → InProcTestAdapter.received."""
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    decision = TriageDecision(intents=[IntentChat(text="hello world")])
    orchestrator = Orchestrator(
        triage=StubTriageService(decision),
        chat=StubChatService("echo: hello world"),
        hub=hub,
    )
    await orchestrator.start()

    await adapter.simulate_inbound("hello world")

    assert len(adapter.received) == 1
    ev = adapter.received[0]
    assert ev.event_type == "completed"
    assert ev.channel == "inproc-test"
    assert ev.session_id == "test-session"
    assert ev.payload["text"] == "echo: hello world"


# ─── Error tolerance ─────────────────────────────────────────────────────


@pytest.mark.local
async def test_triage_failure_does_not_crash_orchestrator() -> None:
    """If triage raises, the message is dropped with a log — no crash."""
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    class FailingTriage:
        async def classify(self, text: str) -> TriageDecision:
            raise RuntimeError("triage is down")

    orchestrator = Orchestrator(
        triage=FailingTriage(),  # type: ignore[arg-type]
        chat=StubChatService("unused"),
        hub=hub,
    )
    await orchestrator.start()

    # Must not raise
    await adapter.simulate_inbound("hello")

    # No events — the message was dropped
    assert adapter.received == []
