"""In-memory async pub/sub primitive for the AzureClaw gateway.

The :class:`GatewayHub` has two routing planes:

1. **Inbound** — every subscriber receives every ``ChannelMessage``. Used
   by the orchestrator (which subscribes once and routes to Triage).
2. **Outbound** — events are routed by ``event.channel`` to the
   subscribers registered for that specific channel. Each channel
   adapter subscribes for its own channel and does not see events
   destined for other channels.

The hub is deliberately in-memory and single-process. When multi-worker
fan-out or durable delivery become real needs (Service Bus for
approvals, Redis for cross-worker pub/sub), the internals can be
swapped without touching the public API.

Subscriber exceptions are logged but do not break the fan-out — one
failing adapter never takes down the others. This is the standard
pub/sub contract.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from azureclaw.gateway.envelope import AgentEvent, ChannelMessage

InboundCallback = Callable[[ChannelMessage], Awaitable[None]]
OutboundCallback = Callable[[AgentEvent], Awaitable[None]]

logger = logging.getLogger(__name__)


class GatewayHub:
    """In-memory async pub/sub for channel messages and agent events."""

    def __init__(self) -> None:
        self._inbound_subscribers: list[InboundCallback] = []
        self._outbound_subscribers: dict[str, list[OutboundCallback]] = {}

    # ─── Inbound ──────────────────────────────────────────────────────

    def subscribe_inbound(self, callback: InboundCallback) -> None:
        """Register a callback to receive every ``ChannelMessage``."""
        self._inbound_subscribers.append(callback)

    async def publish_inbound(self, message: ChannelMessage) -> None:
        """Fan a ``ChannelMessage`` out to every inbound subscriber.

        Exceptions from individual subscribers are logged and swallowed
        so one bad actor cannot break the fan-out.
        """
        for subscriber in self._inbound_subscribers:
            try:
                await subscriber(message)
            except Exception:
                logger.exception(
                    "inbound subscriber raised; continuing fan-out (session_id=%s, channel=%s)",
                    message.session_id,
                    message.channel,
                )

    # ─── Outbound ─────────────────────────────────────────────────────

    def subscribe_outbound(self, channel: str, callback: OutboundCallback) -> None:
        """Register a callback to receive outbound events for one channel."""
        self._outbound_subscribers.setdefault(channel, []).append(callback)

    async def publish_outbound(self, event: AgentEvent) -> None:
        """Route an ``AgentEvent`` to every subscriber for its channel.

        If no subscribers are registered for ``event.channel`` the
        event is dropped with a debug log — the orchestrator should
        never emit events for channels without live adapters, but
        dropping is the right failure mode (adapters can go offline).
        """
        subscribers = self._outbound_subscribers.get(event.channel, [])
        if not subscribers:
            logger.debug(
                "no outbound subscribers for channel=%s event_type=%s; dropping",
                event.channel,
                event.event_type,
            )
            return

        for subscriber in subscribers:
            try:
                await subscriber(event)
            except Exception:
                logger.exception(
                    "outbound subscriber raised; continuing fan-out (channel=%s, event_type=%s)",
                    event.channel,
                    event.event_type,
                )
