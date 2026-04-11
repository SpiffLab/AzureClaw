"""Hermetic in-process channel adapter for integration tests.

Usage in tests::

    hub = GatewayHub()
    adapter = InProcTestAdapter()
    await adapter.start(hub)

    # Register your own inbound subscriber (the orchestrator in real tests)
    async def echo(msg: ChannelMessage) -> None:
        await hub.publish_outbound(AgentEvent(
            event_type="completed",
            channel=msg.channel,
            session_id=msg.session_id,
            payload={"text": f"echo: {msg.text}"},
        ))
    hub.subscribe_inbound(echo)

    # Inject a synthetic inbound message
    await adapter.simulate_inbound("hello world")

    # Assert on what came back out
    assert len(adapter.received) == 1
    assert adapter.received[0].payload["text"] == "echo: hello world"

This adapter's ``name`` is ``"inproc-test"``. Never use it in
production code paths — future channel adapter changes ship the real
platform integrations.
"""

from __future__ import annotations

from fastapi import APIRouter

from azureclaw.gateway.envelope import (
    AgentEvent,
    ApprovalRequest,
    ChannelMessage,
)
from azureclaw.gateway.hub import GatewayHub


class InProcTestAdapter:
    """In-process channel adapter used for hermetic integration tests."""

    name: str = "inproc-test"
    router: APIRouter | None = None

    def __init__(self) -> None:
        self.received: list[AgentEvent] = []
        self._hub: GatewayHub | None = None

    async def start(self, hub: GatewayHub) -> None:
        """Register the adapter against ``hub`` for the ``inproc-test`` channel."""
        self._hub = hub
        hub.subscribe_outbound(self.name, self._on_outbound)

    async def stop(self) -> None:
        """No-op — nothing to clean up."""
        return None

    async def send(self, event: AgentEvent) -> None:
        """Record an outbound event as if it had been rendered."""
        self.received.append(event)

    async def render_approval(self, request: ApprovalRequest) -> None:
        """Record an approval prompt as an outbound event for test assertions."""
        self.received.append(
            AgentEvent(
                event_type="approval_request",
                channel=self.name,
                session_id=request.session_id,
                payload={
                    "approval_id": request.approval_id,
                    "tool": request.tool,
                    "arguments": request.arguments,
                    "site_id": request.site_id,
                },
            )
        )

    async def _on_outbound(self, event: AgentEvent) -> None:
        self.received.append(event)

    async def simulate_inbound(
        self, text: str, session_id: str = "test-session", user_id: str = "test-user"
    ) -> None:
        """Inject a synthetic ``ChannelMessage`` into the hub as if a
        real user had sent it."""
        if self._hub is None:
            raise RuntimeError("InProcTestAdapter.simulate_inbound called before start(hub)")
        message = ChannelMessage(
            channel=self.name,
            session_id=session_id,
            user_id=user_id,
            text=text,
        )
        await self._hub.publish_inbound(message)
