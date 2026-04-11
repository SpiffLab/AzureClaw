"""``ChannelAdapter`` protocol.

Every channel adapter (Discord, WhatsApp, Telegram, iMessage, Teams,
the on-prem bridge, the in-process test fixture) implements this
Protocol. The orchestrator and the gateway hub only ever interact with
adapters through this interface, which keeps the fan-out generic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastapi import APIRouter

from azureclaw.gateway.envelope import AgentEvent, ApprovalRequest
from azureclaw.gateway.hub import GatewayHub


@runtime_checkable
class ChannelAdapter(Protocol):
    """Contract every channel adapter must satisfy."""

    #: Stable channel identifier, e.g., ``"discord"``, ``"telegram"``,
    #: ``"whatsapp"``, ``"imessage"``, ``"teams"``, ``"inproc-test"``.
    name: str

    #: Optional FastAPI router the adapter contributes. Adapters that
    #: use webhook ingress (WhatsApp, Telegram, Teams) expose their
    #: routes here and the gateway mounts them via ``include_router``.
    #: Adapters that use outbound connections (Discord gateway WS,
    #: in-process test adapter) return ``None``.
    router: APIRouter | None

    async def start(self, hub: GatewayHub) -> None:
        """Begin listening for platform-side messages and subscribe to
        outbound events destined for this adapter's channel.
        """
        ...

    async def stop(self) -> None:
        """Gracefully shut down the platform connection."""
        ...

    async def send(self, event: AgentEvent) -> None:
        """Render an agent event as a platform-native message."""
        ...

    async def render_approval(self, request: ApprovalRequest) -> None:
        """Render an HITL approval request as a platform-native
        interactive prompt (buttons / Adaptive Card / etc.).
        """
        ...
