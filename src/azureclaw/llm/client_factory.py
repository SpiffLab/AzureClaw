"""Factory that turns ``config.providers`` into a :class:`BaseChatClient`.

Three per-provider builder functions, one factory that drives them.
The factory:

1. Validates that ``config.providers`` is non-empty
2. Builds an underlying client per declared provider via the
   per-kind builder
3. Returns the single client directly when there is exactly one
   provider; wraps the list in :class:`FailoverChatClient` when there
   are two or more

The Foundry builder takes a credential. The Anthropic builder takes a
:class:`KeyVaultClientLike` so it can resolve ``@kv:`` API keys at
construction time. The Ollama builder needs neither — it talks to a
local OpenAI-compatible endpoint with no auth.

Provider-specific imports are done at the top of this module rather
than lazily, because *every* AzureClaw deploy will have at least one
of these providers. Pulling them in upfront also lets pyright validate
their constructor signatures.
"""

from __future__ import annotations

from typing import Any

from agent_framework import BaseChatClient
from agent_framework.anthropic import AnthropicClient
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient
from openai import AsyncOpenAI

from azureclaw.azure.keyvault import KeyVaultClientLike, resolve_kv_pointer
from azureclaw.config import AzureClawConfig, ProviderConfig
from azureclaw.llm.failover import FailoverChatClient


def _build_foundry_client(provider: ProviderConfig, credential: Any) -> BaseChatClient:
    """Construct a :class:`FoundryChatClient` from a provider config."""
    if not provider.endpoint:
        raise ValueError("Foundry provider requires 'endpoint' to be set in config.providers")
    return FoundryChatClient(
        project_endpoint=provider.endpoint,
        model=provider.model,
        credential=credential,
    )


def _build_anthropic_client(
    provider: ProviderConfig, kv_client: KeyVaultClientLike
) -> BaseChatClient:
    """Construct an :class:`AnthropicClient` from a provider config.

    ``@kv:`` API keys are resolved through ``kv_client`` before the
    real client is constructed. The Anthropic SDK expects an API key
    string at construction time; resolution must complete first.
    """
    resolved_api_key = resolve_kv_pointer(provider.api_key, kv_client)
    if not resolved_api_key:
        raise ValueError("Anthropic provider requires 'api_key' to be set in config.providers")
    return AnthropicClient(api_key=resolved_api_key, model=provider.model)


def _build_ollama_client(provider: ProviderConfig) -> BaseChatClient:
    """Construct an :class:`OpenAIChatClient` pointed at a local Ollama.

    Ollama exposes the OpenAI REST API at ``${base_url}/v1``. We
    construct an :class:`openai.AsyncOpenAI` client with that base URL
    and the literal string ``"ollama"`` as the API key (Ollama ignores
    auth but the OpenAI SDK requires a non-empty value).
    """
    if not provider.base_url:
        raise ValueError("Ollama provider requires 'base_url' to be set in config.providers")
    base_url = provider.base_url.rstrip("/") + "/v1"
    async_client = AsyncOpenAI(base_url=base_url, api_key="ollama")
    return OpenAIChatClient(model=provider.model, async_client=async_client)


def _build_one(
    provider: ProviderConfig, credential: Any, kv_client: KeyVaultClientLike
) -> BaseChatClient:
    """Dispatch to the per-kind builder."""
    if provider.kind == "foundry":
        return _build_foundry_client(provider, credential)
    if provider.kind == "anthropic":
        return _build_anthropic_client(provider, kv_client)
    if provider.kind == "ollama":
        return _build_ollama_client(provider)
    # Defense in depth — Pydantic's Literal already prevents this branch.
    raise ValueError(f"unknown provider kind: {provider.kind!r}")


def build_chat_client(
    config: AzureClawConfig,
    credential: Any,
    kv_client: KeyVaultClientLike,
) -> BaseChatClient:
    """Build the chat client AzureClaw will use to talk to LLMs.

    Args:
        config: A validated :class:`AzureClawConfig`. The function reads
            ``config.providers`` and constructs one client per entry.
        credential: An Azure ``TokenCredential``-like object, used by
            providers (Foundry) that authenticate via Entra ID.
        kv_client: A :class:`KeyVaultClientLike`, used by providers
            (Anthropic) that authenticate via an API key that may be
            stored as an ``@kv:`` pointer.

    Returns:
        - The underlying :class:`BaseChatClient` directly if exactly
          one provider is configured
        - A :class:`FailoverChatClient` wrapping the ordered list when
          two or more providers are configured

    Raises:
        ValueError: if ``config.providers`` is empty, or if any
            provider entry is missing a required field.
    """
    if not config.providers:
        raise ValueError("config.providers is empty; AzureClaw needs at least one LLM provider")

    underlying = [_build_one(provider, credential, kv_client) for provider in config.providers]
    if len(underlying) == 1:
        return underlying[0]
    return FailoverChatClient(providers=underlying)
