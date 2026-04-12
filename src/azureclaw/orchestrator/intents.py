"""Typed intent model for AzureClaw's Triage classifier.

The ``TriageDecision`` model is the single routing contract every later
change respects. Its ``intents`` field is a list of discriminated-union
variants, one per thing the user is asking for. Multiple intents in
one message (e.g., "remind me at 6pm AND summarize this URL") trigger
concurrent fan-out in the orchestrator.

The ``kind`` field on each variant is the discriminator. Pydantic v2
uses it to validate incoming JSON and dispatch ``isinstance`` checks
at runtime.

Usage::

    decision = TriageDecision.model_validate_json(llm_output_json)
    for intent in decision.intents:
        if isinstance(intent, IntentChat):
            ...
        elif isinstance(intent, IntentSchedule):
            ...
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag


class IntentChat(BaseModel):
    """The user wants a conversational reply — no tool use."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["chat"] = "chat"
    text: str = Field(description="The part of the message that is conversational.")


class IntentSchedule(BaseModel):
    """The user wants a reminder or scheduled action."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["schedule"] = "schedule"
    description: str = Field(description="What to schedule or remind about.")
    when: str = Field(
        description="Natural-language time expression (e.g., 'in 5 minutes', 'at 6pm')."
    )


class IntentResearch(BaseModel):
    """The user wants a URL browsed / content summarized / information looked up."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["research"] = "research"
    query: str = Field(description="What to research, browse, or summarize.")
    url: str | None = Field(default=None, description="Optional URL to browse.")


class IntentOnPrem(BaseModel):
    """The user wants something done at an on-prem site via the connector."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["onprem"] = "onprem"
    site_id: str = Field(description="Which registered site to target (e.g., 'home', 'mac').")
    action: str = Field(
        description="What to do at the site (e.g., 'list shares on NAS', 'restart pihole')."
    )


def _intent_discriminator(v: object) -> str:  # pyright: ignore[reportReturnType]
    """Extract the discriminator value for the Intent union.

    Pydantic passes raw dicts or model instances depending on the
    validation stage. Pyright cannot narrow ``dict[Unknown, Unknown]``
    cleanly so we suppress the related diagnostics here.
    """
    if isinstance(v, dict):
        return str(v.get("kind", "chat"))  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
    return str(getattr(v, "kind", "chat"))


Intent = Annotated[
    Annotated[IntentChat, Tag("chat")]
    | Annotated[IntentSchedule, Tag("schedule")]
    | Annotated[IntentResearch, Tag("research")]
    | Annotated[IntentOnPrem, Tag("onprem")],
    Discriminator(_intent_discriminator),  # pyright: ignore[reportUnknownArgumentType]
]
"""Discriminated union of all intent variants."""


class TriageDecision(BaseModel):
    """Root model produced by the Triage agent.

    A single user message may contain multiple intents (e.g., "remind me
    at 6pm AND summarize this recipe"). The orchestrator processes them
    concurrently via ``asyncio.gather``.
    """

    model_config = ConfigDict(extra="forbid")

    intents: list[Intent] = Field(
        min_length=1,
        description="One or more intents extracted from the user's message.",
    )
