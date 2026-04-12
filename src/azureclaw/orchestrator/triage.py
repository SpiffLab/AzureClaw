"""MAF-backed triage service — classifies user messages into intents.

Production code. NOT exercised by ``pytest -m local`` because it
requires a real ``BaseChatClient`` with provider credentials. Tests
use ``StubTriageService`` instead.
"""

from __future__ import annotations

from agent_framework import BaseChatClient

from azureclaw.orchestrator.intents import TriageDecision

TRIAGE_PROMPT = """\
You are a triage classifier for AzureClaw, a multi-channel AI assistant.
Your job is to read the user's message and decide what they want.

Respond with JSON matching the TriageDecision schema. The "intents" array
should contain one object per distinct thing the user is asking for. Each
object must have a "kind" field that is one of:

- "chat"     — the user wants a conversational reply (no tool use)
- "schedule" — the user wants a reminder or scheduled action
- "research" — the user wants a URL browsed or information looked up
- "onprem"   — the user wants something done at an on-prem site

A single message may contain multiple intents. For example:
  "remind me at 6pm to defrost the lobster and also summarize https://example.com/recipe"
produces two intents: one schedule and one research.

When in doubt, classify as "chat".
"""


class MAFTriageService:
    """Wraps a ``ChatAgent`` with ``response_format=TriageDecision``."""

    def __init__(self, chat_client: BaseChatClient) -> None:
        self._agent = chat_client.as_agent(
            name="Triage",
            instructions=TRIAGE_PROMPT,
            default_options={"response_format": TriageDecision},
        )

    async def classify(self, text: str) -> TriageDecision:
        response = await self._agent.run(text)
        decision = response.value
        if decision is None:
            # Fallback: if structured output parsing failed, treat
            # the entire message as a chat intent.
            from azureclaw.orchestrator.intents import IntentChat

            decision = TriageDecision(intents=[IntentChat(text=text)])
        return decision
