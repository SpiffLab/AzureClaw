"""Tests for the intent discriminated union model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from azureclaw.orchestrator.intents import (
    IntentChat,
    IntentOnPrem,
    IntentResearch,
    IntentSchedule,
    TriageDecision,
)


@pytest.mark.local
def test_single_chat_intent_round_trips() -> None:
    original = TriageDecision(intents=[IntentChat(text="hello")])
    payload = original.model_dump(mode="json")
    reconstructed = TriageDecision.model_validate(payload)
    assert reconstructed == original
    assert isinstance(reconstructed.intents[0], IntentChat)


@pytest.mark.local
def test_multi_intent_preserves_all_variants() -> None:
    original = TriageDecision(
        intents=[
            IntentChat(text="hello"),
            IntentSchedule(description="remind me", when="5pm"),
            IntentResearch(query="summarize recipe", url="https://example.com"),
            IntentOnPrem(site_id="home", action="list shares"),
        ]
    )
    payload = original.model_dump(mode="json")
    reconstructed = TriageDecision.model_validate(payload)
    assert len(reconstructed.intents) == 4
    assert isinstance(reconstructed.intents[0], IntentChat)
    assert isinstance(reconstructed.intents[1], IntentSchedule)
    assert isinstance(reconstructed.intents[2], IntentResearch)
    assert isinstance(reconstructed.intents[3], IntentOnPrem)


@pytest.mark.local
def test_unknown_kind_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        TriageDecision.model_validate({"intents": [{"kind": "nope"}]})


@pytest.mark.local
def test_empty_intents_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        TriageDecision(intents=[])


@pytest.mark.local
@pytest.mark.parametrize(
    "intent",
    [
        IntentChat(text="hello"),
        IntentSchedule(description="remind me", when="now"),
        IntentResearch(query="search"),
        IntentOnPrem(site_id="home", action="wake nas"),
    ],
    ids=["chat", "schedule", "research", "onprem"],
)
def test_each_intent_kind_is_valid(intent: object) -> None:
    decision = TriageDecision(intents=[intent])  # type: ignore[list-item]
    assert len(decision.intents) == 1


@pytest.mark.local
def test_triage_decision_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TriageDecision.model_validate(
            {"intents": [{"kind": "chat", "text": "hi"}], "extra_field": "nope"}
        )
