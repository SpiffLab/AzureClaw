"""AzureClaw — an Azure-native Microsoft Agent Framework re-imagining of OpenClaw.

This package is intentionally minimal in the bootstrap-skeleton change. The
real surface (gateway, orchestrator, adapters, tools, middleware, memory)
lands incrementally through subsequent OpenSpec changes under
``openspec/changes/``.
"""

# `__version__` lives in `_version.py` so routes / observability can
# import it without pulling in the full package surface. See
# `azureclaw/_version.py` for the rationale.
from azureclaw._version import __version__
from azureclaw.adapters.base import ChannelAdapter
from azureclaw.config import AzureClawConfig
from azureclaw.gateway.app import create_app
from azureclaw.gateway.envelope import (
    AgentEvent,
    ApprovalRequest,
    ChannelMessage,
)
from azureclaw.gateway.hub import GatewayHub
from azureclaw.llm import FailoverChatClient, ProviderExhausted, build_chat_client
from azureclaw.observability import setup_observability

__all__ = [
    "AgentEvent",
    "ApprovalRequest",
    "AzureClawConfig",
    "ChannelAdapter",
    "ChannelMessage",
    "FailoverChatClient",
    "GatewayHub",
    "ProviderExhausted",
    "__version__",
    "build_chat_client",
    "create_app",
    "setup_observability",
]
