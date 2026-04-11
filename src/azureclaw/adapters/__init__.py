"""Channel adapters for AzureClaw.

Each adapter normalizes a platform-native event stream (Discord,
WhatsApp, Telegram, iMessage, Microsoft Teams) into the common
:class:`azureclaw.gateway.envelope.ChannelMessage` and
:class:`AgentEvent` envelopes, and subscribes to the
:class:`GatewayHub` for outbound events destined for its channel.

This subpackage ships two things in the ``gateway-and-webhooks``
OpenSpec change:

- :class:`ChannelAdapter` — the Protocol every adapter implements
- :class:`InProcTestAdapter` — a hermetic test fixture

Real channel adapters land with their own OpenSpec changes (#11, #12,
#19, #20, #21, #22).
"""

from azureclaw.adapters.base import ChannelAdapter
from azureclaw.adapters.inproc_test_adapter import InProcTestAdapter

__all__ = ["ChannelAdapter", "InProcTestAdapter"]
