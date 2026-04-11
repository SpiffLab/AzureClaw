"""AzureClaw gateway — the FastAPI control plane.

Exposes :func:`create_app`, the canonical factory every entry point
(including ``uvicorn azureclaw.gateway.app:get_app --factory``) uses to
build the FastAPI application. The app's lifespan wires
:func:`azureclaw.setup_observability` at startup and attaches a shared
:class:`GatewayHub` to ``app.state.hub``.

Later OpenSpec changes contribute additional routers (one per channel
adapter), subscribers to the hub (the orchestrator, the Magentic team),
and middleware (safety filter, audit).
"""

from azureclaw.gateway.app import create_app, get_app
from azureclaw.gateway.envelope import AgentEvent, ApprovalRequest, ChannelMessage
from azureclaw.gateway.hub import GatewayHub

__all__ = [
    "AgentEvent",
    "ApprovalRequest",
    "ChannelMessage",
    "GatewayHub",
    "create_app",
    "get_app",
]
