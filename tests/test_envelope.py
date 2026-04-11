"""Tests for the gateway envelope models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from azureclaw import AgentEvent, ApprovalRequest, ChannelMessage

# ─── ChannelMessage ──────────────────────────────────────────────────────


@pytest.mark.local
def test_channel_message_round_trips_through_json() -> None:
    original = ChannelMessage(
        channel="inproc-test",
        session_id="s1",
        user_id="u1",
        text="hello world",
        attachments=[{"kind": "image", "url": "https://example.com/a.png"}],
        metadata={"origin": "test"},
    )

    payload = original.model_dump(mode="json")
    reconstructed = ChannelMessage.model_validate(payload)

    assert reconstructed == original


@pytest.mark.local
def test_channel_message_defaults_attachments_and_metadata() -> None:
    msg = ChannelMessage(channel="telegram", session_id="s", user_id="u", text="hi")
    assert msg.attachments == []
    assert msg.metadata == {}
    assert isinstance(msg.timestamp, datetime)


@pytest.mark.local
def test_channel_message_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ChannelMessage.model_validate(
            {
                "channel": "x",
                "session_id": "s",
                "user_id": "u",
                "text": "hi",
                "unknown_field": "surprise",
            }
        )


# ─── AgentEvent ──────────────────────────────────────────────────────────


@pytest.mark.local
@pytest.mark.parametrize(
    "event_type",
    ["text_delta", "tool_call", "tool_result", "approval_request", "completed"],
)
def test_agent_event_accepts_every_documented_event_type(event_type: str) -> None:
    ev = AgentEvent(
        event_type=event_type,  # type: ignore[arg-type]
        channel="inproc-test",
        session_id="s",
        payload={"whatever": 1},
    )
    assert ev.event_type == event_type


@pytest.mark.local
def test_agent_event_rejects_unknown_event_type() -> None:
    with pytest.raises(ValidationError):
        AgentEvent.model_validate(
            {
                "event_type": "nope",
                "channel": "x",
                "session_id": "s",
            }
        )


@pytest.mark.local
def test_agent_event_round_trips_through_json() -> None:
    ev = AgentEvent(
        event_type="completed",
        channel="discord",
        session_id="s",
        payload={"text": "done", "tokens": 42},
    )
    payload = ev.model_dump(mode="json")
    reconstructed = AgentEvent.model_validate(payload)
    assert reconstructed == ev


# ─── ApprovalRequest ─────────────────────────────────────────────────────


@pytest.mark.local
def test_approval_request_has_uuid_approval_id_by_default() -> None:
    req = ApprovalRequest(tool="cron_tool", session_id="s", channel="telegram")
    # Two requests in quick succession must still produce different ids
    other = ApprovalRequest(tool="cron_tool", session_id="s", channel="telegram")
    assert req.approval_id != other.approval_id
    assert len(req.approval_id) >= 32  # UUID4 str length check


@pytest.mark.local
def test_approval_request_round_trips_through_json() -> None:
    req = ApprovalRequest(
        tool="post_to_discord",
        arguments={"channel_id": "abc", "text": "hi"},
        session_id="s",
        channel="slack",
        site_id=None,
    )
    payload = req.model_dump(mode="json")
    reconstructed = ApprovalRequest.model_validate(payload)
    assert reconstructed == req


@pytest.mark.local
def test_approval_request_site_id_carries_onprem_context() -> None:
    req = ApprovalRequest(
        tool="ssh_tool",
        arguments={"host": "pi.local", "command": "systemctl restart pihole"},
        session_id="s",
        channel="discord",
        site_id="home",
    )
    assert req.site_id == "home"
