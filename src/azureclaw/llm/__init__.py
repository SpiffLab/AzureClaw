"""LLM provider stack for AzureClaw.

Re-exports the public surface every caller (the orchestrator, agents,
test fixtures) needs from one import:

- :func:`build_chat_client` — the factory that turns
  ``config.providers`` into a single :class:`agent_framework.BaseChatClient`.
- :class:`FailoverChatClient` — the wrapping client that retries on
  transient errors.
- :class:`ProviderExhausted` — the exception raised when every provider
  fails.

Each later change adds the per-provider subpackage it actually needs;
this module already pulls in the Foundry, Anthropic, and OpenAI (used
for Ollama) packages because they're foundational to every agent run.
"""

from azureclaw.llm.client_factory import build_chat_client
from azureclaw.llm.failover import FailoverChatClient, ProviderExhausted

__all__ = ["FailoverChatClient", "ProviderExhausted", "build_chat_client"]
