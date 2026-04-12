"""The AzureClaw orchestrator — dispatches inbound messages by intent.

The ``Orchestrator`` subscribes to the gateway hub's inbound channel.
When a ``ChannelMessage`` arrives, it classifies via the
``TriageService``, then dispatches each intent to the appropriate
handler. ``IntentChat`` delegates to the ``ChatService``; the other
three intent types (Schedule, Research, OnPrem) emit stub events
that later OpenSpec changes replace with real implementations.

Multiple intents fan out concurrently via ``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
import logging

from azureclaw.gateway.envelope import AgentEvent, ChannelMessage
from azureclaw.gateway.hub import GatewayHub
from azureclaw.orchestrator.intents import (
    Intent,
    IntentChat,
    IntentOnPrem,
    IntentResearch,
    IntentSchedule,
)
from azureclaw.orchestrator.services import ChatService, TriageService

logger = logging.getLogger(__name__)


class Orchestrator:
    """Subscribes to the hub, classifies inbound messages, dispatches by intent."""

    def __init__(
        self,
        triage: TriageService,
        chat: ChatService,
        hub: GatewayHub,
    ) -> None:
        self._triage = triage
        self._chat = chat
        self._hub = hub

    async def start(self) -> None:
        """Subscribe to the hub's inbound channel."""
        self._hub.subscribe_inbound(self._handle_inbound)

    async def _handle_inbound(self, msg: ChannelMessage) -> None:
        """Classify the message and dispatch each intent."""
        try:
            decision = await self._triage.classify(msg.text)
        except Exception:
            logger.exception(
                "triage failed for session_id=%s channel=%s; dropping message",
                msg.session_id,
                msg.channel,
            )
            return

        if len(decision.intents) == 1:
            await self._handle_intent(decision.intents[0], msg)
        else:
            # Fan out multiple intents concurrently.
            results = await asyncio.gather(
                *(self._handle_intent(intent, msg) for intent in decision.intents),
                return_exceptions=True,
            )
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    logger.exception(
                        "intent handler %d failed for session_id=%s: %s",
                        i,
                        msg.session_id,
                        result,
                    )

    async def _handle_intent(self, intent: Intent, msg: ChannelMessage) -> None:
        """Dispatch a single intent to the appropriate handler."""
        if isinstance(intent, IntentChat):
            reply = await self._chat.respond(intent.text, msg.session_id)
            await self._hub.publish_outbound(
                AgentEvent(
                    event_type="completed",
                    channel=msg.channel,
                    session_id=msg.session_id,
                    payload={"text": reply},
                )
            )
        elif isinstance(intent, IntentSchedule):
            await self._hub.publish_outbound(
                AgentEvent(
                    event_type="completed",
                    channel=msg.channel,
                    session_id=msg.session_id,
                    payload={
                        "stub": True,
                        "change_ref": "approval-loop-servicebus",
                        "intent": intent.model_dump(),
                    },
                )
            )
        elif isinstance(intent, IntentResearch):
            await self._hub.publish_outbound(
                AgentEvent(
                    event_type="completed",
                    channel=msg.channel,
                    session_id=msg.session_id,
                    payload={
                        "stub": True,
                        "change_ref": "magentic-research-team",
                        "intent": intent.model_dump(),
                    },
                )
            )
        elif isinstance(intent, IntentOnPrem):  # pyright: ignore[reportUnnecessaryIsInstance]
            await self._hub.publish_outbound(
                AgentEvent(
                    event_type="completed",
                    channel=msg.channel,
                    session_id=msg.session_id,
                    payload={
                        "stub": True,
                        "change_ref": "onprem-peer-a2a",
                        "intent": intent.model_dump(),
                    },
                )
            )
        else:
            logger.warning("unknown intent type %s; dropping", type(intent).__name__)
