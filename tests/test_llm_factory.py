"""Tests for ``azureclaw.llm.client_factory.build_chat_client``."""

from __future__ import annotations

import pytest

import azureclaw
from azureclaw import (
    AzureClawConfig,
    FailoverChatClient,
    build_chat_client,
)
from azureclaw.azure.keyvault import _LocalStubKeyVaultClient  # pyright: ignore[reportPrivateUsage]
from azureclaw.config import ProviderConfig


@pytest.fixture
def kv_with_anthropic_secret() -> _LocalStubKeyVaultClient:
    return _LocalStubKeyVaultClient(secrets={"anthropic-api-key": "sk-ant-test"})


@pytest.fixture
def empty_kv() -> _LocalStubKeyVaultClient:
    return _LocalStubKeyVaultClient()


# ─── Empty providers ─────────────────────────────────────────────────────


@pytest.mark.local
def test_empty_providers_raises_value_error(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    cfg = AzureClawConfig(environment="local")
    with pytest.raises(ValueError, match="providers"):
        build_chat_client(cfg, credential=None, kv_client=empty_kv)


# ─── Single provider returns underlying client directly ─────────────────


@pytest.mark.local
def test_single_foundry_provider_returns_foundry_client(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    from agent_framework.foundry import FoundryChatClient

    cfg = AzureClawConfig(
        environment="local",
        providers=[
            ProviderConfig(
                kind="foundry",
                model="gpt-5.4-mini",
                endpoint="https://example.services.ai.azure.com/api/projects/p",
            )
        ],
    )

    client = build_chat_client(cfg, credential="stub-cred", kv_client=empty_kv)

    assert isinstance(client, FoundryChatClient)
    assert not isinstance(client, FailoverChatClient)


@pytest.mark.local
def test_single_anthropic_provider_returns_anthropic_client(
    kv_with_anthropic_secret: _LocalStubKeyVaultClient,
) -> None:
    from agent_framework.anthropic import AnthropicClient

    cfg = AzureClawConfig(
        environment="local",
        providers=[
            ProviderConfig(
                kind="anthropic",
                model="claude-opus-4-6",
                api_key="@kv:anthropic-api-key",
            )
        ],
    )

    client = build_chat_client(cfg, credential=None, kv_client=kv_with_anthropic_secret)

    assert isinstance(client, AnthropicClient)


@pytest.mark.local
def test_single_ollama_provider_returns_openai_client(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    from agent_framework.openai import OpenAIChatClient

    cfg = AzureClawConfig(
        environment="local",
        providers=[
            ProviderConfig(kind="ollama", model="llama3.3", base_url="http://localhost:11434")
        ],
    )

    client = build_chat_client(cfg, credential=None, kv_client=empty_kv)

    assert isinstance(client, OpenAIChatClient)


# ─── Multiple providers wrap in failover ─────────────────────────────────


@pytest.mark.local
def test_three_providers_wrap_in_failover(
    kv_with_anthropic_secret: _LocalStubKeyVaultClient,
) -> None:
    cfg = AzureClawConfig(
        environment="local",
        providers=[
            ProviderConfig(
                kind="foundry",
                model="gpt-5.4-mini",
                endpoint="https://example.services.ai.azure.com/api/projects/p",
            ),
            ProviderConfig(
                kind="anthropic",
                model="claude-opus-4-6",
                api_key="@kv:anthropic-api-key",
            ),
            ProviderConfig(kind="ollama", model="llama3.3", base_url="http://localhost:11434"),
        ],
    )

    client = build_chat_client(cfg, credential="stub", kv_client=kv_with_anthropic_secret)

    assert isinstance(client, FailoverChatClient)
    assert len(client._providers) == 3  # pyright: ignore[reportPrivateUsage]


# ─── Foundry validation ─────────────────────────────────────────────────


@pytest.mark.local
def test_foundry_provider_without_endpoint_raises(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    cfg = AzureClawConfig(
        environment="local",
        providers=[ProviderConfig(kind="foundry", model="gpt-5.4-mini")],
    )

    with pytest.raises(ValueError, match="endpoint"):
        build_chat_client(cfg, credential="stub", kv_client=empty_kv)


# ─── Anthropic validation ───────────────────────────────────────────────


@pytest.mark.local
def test_anthropic_provider_without_api_key_raises(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    cfg = AzureClawConfig(
        environment="local",
        providers=[ProviderConfig(kind="anthropic", model="claude-opus-4-6")],
    )

    with pytest.raises(ValueError, match="api_key"):
        build_chat_client(cfg, credential=None, kv_client=empty_kv)


@pytest.mark.local
def test_anthropic_provider_resolves_kv_api_key(
    kv_with_anthropic_secret: _LocalStubKeyVaultClient,
) -> None:
    """The Anthropic builder must call the resolver before constructing
    the SDK client."""
    from agent_framework.anthropic import AnthropicClient

    cfg = AzureClawConfig(
        environment="local",
        providers=[
            ProviderConfig(
                kind="anthropic",
                model="claude-opus-4-6",
                api_key="@kv:anthropic-api-key",
            )
        ],
    )

    client = build_chat_client(cfg, credential=None, kv_client=kv_with_anthropic_secret)

    assert isinstance(client, AnthropicClient)


@pytest.mark.local
def test_anthropic_provider_unresolvable_kv_pointer_propagates_keyerror(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    cfg = AzureClawConfig(
        environment="local",
        providers=[
            ProviderConfig(
                kind="anthropic",
                model="claude-opus-4-6",
                api_key="@kv:does-not-exist",
            )
        ],
    )

    with pytest.raises(KeyError, match="does-not-exist"):
        build_chat_client(cfg, credential=None, kv_client=empty_kv)


# ─── Ollama validation ──────────────────────────────────────────────────


@pytest.mark.local
def test_ollama_provider_without_base_url_raises(
    empty_kv: _LocalStubKeyVaultClient,
) -> None:
    cfg = AzureClawConfig(
        environment="local",
        providers=[ProviderConfig(kind="ollama", model="llama3.3")],
    )

    with pytest.raises(ValueError, match="base_url"):
        build_chat_client(cfg, credential=None, kv_client=empty_kv)


# ─── Re-exports ──────────────────────────────────────────────────────────


@pytest.mark.local
def test_build_chat_client_is_re_exported_from_package_root() -> None:
    assert hasattr(azureclaw, "build_chat_client")
    assert azureclaw.build_chat_client is build_chat_client
    assert "build_chat_client" in azureclaw.__all__
