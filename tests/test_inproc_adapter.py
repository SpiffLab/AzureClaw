"""End-to-end tests for the in-process adapter + hub round-trip."""

from __future__ import annotations

import pytest

from azureclaw import (
    AgentEvent,
    ApprovalRequest,
    ChannelMessage,
    GatewayHub,
)
from azureclaw.adapters import InProcTestAdapter


@pytest.mark.local
async def test_simulate_inbound_delivers_to_hub_subscriber() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    received: list[ChannelMessage] = []

    async def collect(msg: ChannelMessage) -> None:
        received.append(msg)

    hub.subscribe_inbound(collect)

    await adapter.simulate_inbound("hello world", session_id="test-abc")

    assert len(received) == 1
    assert received[0].text == "hello world"
    assert received[0].channel == "inproc-test"
    assert received[0].session_id == "test-abc"


@pytest.mark.local
async def test_outbound_events_land_in_received() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    event = AgentEvent(
        event_type="completed",
        channel="inproc-test",
        session_id="s",
        payload={"text": "done"},
    )
    await hub.publish_outbound(event)

    assert adapter.received == [event]


@pytest.mark.local
async def test_end_to_end_echo_round_trip() -> None:
    """Prove the whole pipeline works without any real channel.

    This is the first end-to-end integration test in the repo: a
    synthetic inbound message is processed by an echo subscriber that
    publishes an outbound event, which the in-process adapter receives
    on its ``received`` list.
    """
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    async def echo(msg: ChannelMessage) -> None:
        await hub.publish_outbound(
            AgentEvent(
                event_type="completed",
                channel=msg.channel,
                session_id=msg.session_id,
                payload={"text": f"echo: {msg.text}"},
            )
        )

    hub.subscribe_inbound(echo)

    await adapter.simulate_inbound("hello world")

    assert len(adapter.received) == 1
    assert adapter.received[0].event_type == "completed"
    assert adapter.received[0].payload["text"] == "echo: hello world"


@pytest.mark.local
async def test_render_approval_produces_an_agent_event() -> None:
    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    request = ApprovalRequest(
        tool="cron_tool",
        arguments={"when": "in 5 minutes", "message": "defrost lobster"},
        session_id="s",
        channel="inproc-test",
    )
    await adapter.render_approval(request)

    assert len(adapter.received) == 1
    rendered = adapter.received[0]
    assert rendered.event_type == "approval_request"
    assert rendered.payload["approval_id"] == request.approval_id
    assert rendered.payload["tool"] == "cron_tool"


@pytest.mark.local
async def test_simulate_inbound_before_start_raises() -> None:
    adapter = InProcTestAdapter()
    with pytest.raises(RuntimeError, match="before start"):
        await adapter.simulate_inbound("hello")
