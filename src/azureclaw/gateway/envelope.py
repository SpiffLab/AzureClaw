"""Strongly-typed envelopes used at every gateway boundary.

Three models:

- :class:`ChannelMessage` — inbound (user → gateway). Normalized by each
  channel adapter from its platform-native event shape.
- :class:`AgentEvent` — outbound (orchestrator → gateway → channel
  adapter). Each adapter renders the event in its platform-native UI.
- :class:`ApprovalRequest` — HITL. Emitted when a tool marked
  ``require_approval=True`` is about to run; the channel adapter
  renders it as an interactive prompt and the user's response resumes
  the workflow via the ``/approvals`` route (wired in
  ``approval-loop-servicebus``, OpenSpec change #10).

Every model forbids extra fields so stray keys fail loudly at the
boundary rather than silently propagating.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp suitable for envelope fields."""
    return datetime.now(UTC)


class ChannelMessage(BaseModel):
    """A normalized inbound message from any channel adapter.

    Every channel adapter converts its platform-native payload (a Discord
    message, a WhatsApp webhook, an iMessage via BlueBubbles, etc.) into
    this envelope before publishing it to the gateway hub.
    """

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(
        description="Stable channel identifier (e.g., 'telegram', 'discord', 'inproc-test')."
    )
    session_id: str = Field(
        description=(
            "Stable per-conversation identifier. "
            "Multi-user chats derive this from channel+room+user."
        )
    )
    user_id: str = Field(description="Platform-native user id.")
    text: str = Field(description="The message text content.")
    attachments: list[dict[str, Any]] = Field(
        default_factory=lambda: [],
        description="Platform-native attachment metadata (urls, mime types, sizes).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=lambda: {},
        description="Platform-specific extras the adapter wants to preserve.",
    )
    timestamp: datetime = Field(
        default_factory=_utcnow,
        description="When the gateway received the message (not when the user sent it).",
    )


AgentEventType = Literal[
    "text_delta",
    "tool_call",
    "tool_result",
    "approval_request",
    "completed",
]


class AgentEvent(BaseModel):
    """An outbound event from the orchestrator to a channel adapter.

    Every agent turn emits a stream of these: ``text_delta`` for
    streaming chunks, ``tool_call`` / ``tool_result`` for tool
    invocations, ``approval_request`` for HITL, and a final
    ``completed`` to signal the turn is done.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: AgentEventType = Field(
        description="The event kind. Locks callers into one of five values."
    )
    channel: str = Field(
        description="Target channel. The hub routes outbound events by this field."
    )
    session_id: str = Field(description="The session this event belongs to.")
    payload: dict[str, Any] = Field(
        default_factory=lambda: {},
        description=(
            "Event-type-specific shape. See docs/runbooks/observability.md for the expected keys."
        ),
    )
    timestamp: datetime = Field(default_factory=_utcnow)


class ApprovalRequest(BaseModel):
    """A human-in-the-loop approval request.

    Created when a tool marked ``require_approval=True`` is about to
    execute. The channel adapter renders this as an interactive prompt
    and the user's response routes back through Service Bus to resume
    or cancel the workflow.
    """

    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique id for this request; the user's response echoes it back.",
    )
    tool: str = Field(description="The tool function name awaiting approval.")
    arguments: dict[str, Any] = Field(
        default_factory=lambda: {},
        description="The tool's arguments the user is being asked to authorize.",
    )
    session_id: str = Field(description="The session requesting approval.")
    channel: str = Field(description="The channel that should render the prompt.")
    requested_at: datetime = Field(default_factory=_utcnow)
    site_id: str | None = Field(
        default=None,
        description="For on-prem tool calls, the site the tool runs at. None for cloud tools.",
    )
