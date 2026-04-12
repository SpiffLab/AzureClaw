"""MAF-backed chat service — produces conversational replies.

Production code. NOT exercised by ``pytest -m local`` because it
requires a real ``BaseChatClient`` with provider credentials. Tests
use ``StubChatService`` instead.
"""

from __future__ import annotations

from agent_framework import BaseChatClient

CHAT_PROMPT = """\
You are AzureClaw, a friendly and helpful personal AI assistant.
Keep your responses concise, clear, and conversational.
"""


class MAFChatService:
    """Wraps a ``ChatAgent`` and returns the text response."""

    def __init__(self, chat_client: BaseChatClient) -> None:
        self._agent = chat_client.as_agent(
            name="Chat",
            instructions=CHAT_PROMPT,
        )

    async def respond(self, text: str, session_id: str) -> str:
        response = await self._agent.run(text)
        return response.text or ""
