"""Tests for the ``GatewayHub`` pub/sub primitive."""

from __future__ import annotations

import logging

import pytest

from azureclaw import AgentEvent, ChannelMessage, GatewayHub


def _msg(channel: str = "inproc-test", text: str = "hello") -> ChannelMessage:
    return ChannelMessage(
        channel=channel,
        session_id="s",
        user_id="u",
        text=text,
    )


def _event(channel: str = "inproc-test", text: str = "ok") -> AgentEvent:
    return AgentEvent(
        event_type="completed",
        channel=channel,
        session_id="s",
        payload={"text": text},
    )


# ─── Inbound fan-out ─────────────────────────────────────────────────────


@pytest.mark.local
async def test_inbound_publishes_to_every_subscriber() -> None:
    hub = GatewayHub()
    received_a: list[ChannelMessage] = []
    received_b: list[ChannelMessage] = []

    async def collect_a(m: ChannelMessage) -> None:
        received_a.append(m)

    async def collect_b(m: ChannelMessage) -> None:
        received_b.append(m)

    hub.subscribe_inbound(collect_a)
    hub.subscribe_inbound(collect_b)

    msg = _msg(text="hello")
    await hub.publish_inbound(msg)

    assert received_a == [msg]
    assert received_b == [msg]


@pytest.mark.local
async def test_inbound_raising_subscriber_does_not_break_fanout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    hub = GatewayHub()
    received: list[ChannelMessage] = []

    async def bad(m: ChannelMessage) -> None:
        raise RuntimeError("boom")

    async def good(m: ChannelMessage) -> None:
        received.append(m)

    hub.subscribe_inbound(bad)
    hub.subscribe_inbound(good)

    with caplog.at_level(logging.ERROR):
        await hub.publish_inbound(_msg())

    assert len(received) == 1
    assert any("inbound subscriber raised" in rec.message for rec in caplog.records)


# ─── Outbound channel routing ────────────────────────────────────────────


@pytest.mark.local
async def test_outbound_routes_to_matching_channel_only() -> None:
    hub = GatewayHub()
    telegram_received: list[AgentEvent] = []
    discord_received: list[AgentEvent] = []

    async def on_telegram(ev: AgentEvent) -> None:
        telegram_received.append(ev)

    async def on_discord(ev: AgentEvent) -> None:
        discord_received.append(ev)

    hub.subscribe_outbound("telegram", on_telegram)
    hub.subscribe_outbound("discord", on_discord)

    await hub.publish_outbound(_event(channel="telegram", text="hi tg"))

    assert len(telegram_received) == 1
    assert discord_received == []


@pytest.mark.local
async def test_outbound_with_no_matching_subscribers_is_noop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    hub = GatewayHub()
    # No subscribers registered at all
    with caplog.at_level(logging.DEBUG):
        await hub.publish_outbound(_event(channel="ghost", text="nobody home"))

    assert any("no outbound subscribers" in rec.message for rec in caplog.records)


@pytest.mark.local
async def test_outbound_raising_subscriber_does_not_break_fanout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    hub = GatewayHub()
    received: list[AgentEvent] = []

    async def bad(ev: AgentEvent) -> None:
        raise RuntimeError("down")

    async def good(ev: AgentEvent) -> None:
        received.append(ev)

    hub.subscribe_outbound("discord", bad)
    hub.subscribe_outbound("discord", good)

    with caplog.at_level(logging.ERROR):
        await hub.publish_outbound(_event(channel="discord"))

    assert len(received) == 1
    assert any("outbound subscriber raised" in rec.message for rec in caplog.records)
