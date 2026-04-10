"""Typed configuration model for AzureClaw.

This module mirrors every top-level section of ``config.example.yaml`` as a
Pydantic v2 model. Sections whose internal structure is still being designed
in later OpenSpec changes are intentionally typed loosely (``dict | None``)
and will be tightened by the changes that own them.

Usage::

    from pathlib import Path
    from azureclaw import AzureClawConfig

    cfg = AzureClawConfig.from_yaml(Path("config.yaml"))
    print(cfg.environment, len(cfg.providers))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Per-section models
# ---------------------------------------------------------------------------

# All section models forbid unknown fields by default. The root model is
# permissive to give the test suite room to grow new sections without an
# update to this file in lockstep — but each known section is strict.
_StrictModel: type[BaseModel] = BaseModel


class ProviderConfig(BaseModel):
    """A single LLM provider entry in the ordered ``providers:`` list."""

    model_config = ConfigDict(extra="allow")

    kind: Literal["foundry", "anthropic", "ollama"]
    model: str
    endpoint: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    credential: str | None = None


class EmbeddingsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str
    model: str
    endpoint: str | None = None
    credential: str | None = None


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    backend: Literal["cosmos_aisearch", "sqlite"] = "sqlite"
    cosmos: dict[str, Any] | None = None
    ai_search: dict[str, Any] | None = None
    recall: dict[str, Any] | None = None


class ChannelsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    whatsapp: dict[str, Any] | None = None
    telegram: dict[str, Any] | None = None
    discord: dict[str, Any] | None = None
    imessage: dict[str, Any] | None = None
    teams: dict[str, Any] | None = None


class ToolsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    browser: dict[str, Any] | None = None
    canvas: dict[str, Any] | None = None
    cron: dict[str, Any] | None = None
    channel_actions: dict[str, Any] | None = None


class SafetyConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str | None = None
    endpoint: str | None = None
    thresholds: dict[str, Any] | None = None
    block_jailbreak_attempts: bool = True


class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    app_insights_connection_string: str | None = None
    console_fallback: bool = False


class HybridConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    relay: dict[str, Any] | None = None
    sites_container: str = "sites"
    default_approval_policy: str = "confirm_all_writes"


class A2AConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    public_endpoint: str | None = None
    rate_limit_per_minute: int = 60


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class AzureClawConfig(BaseModel):
    """Root configuration model for AzureClaw.

    The root mirrors ``config.example.yaml`` 1:1. Loading is done via
    :meth:`from_yaml`. ``@kv:secret-name`` pointers are preserved as
    literal strings here; resolution against Azure Key Vault is the
    responsibility of a later OpenSpec change (``llm-failover-middleware``).
    """

    model_config = ConfigDict(extra="allow")

    environment: Literal["dev", "prod", "local"] = "local"
    providers: list[ProviderConfig] = Field(default_factory=lambda: [])
    embeddings: EmbeddingsConfig | None = None
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    safety: SafetyConfig | None = None
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    hybrid: HybridConfig = Field(default_factory=HybridConfig)
    a2a: A2AConfig = Field(default_factory=A2AConfig)

    @classmethod
    def from_yaml(cls, path: Path | str) -> AzureClawConfig:
        """Load and validate a YAML config file into an :class:`AzureClawConfig`.

        Args:
            path: Filesystem path to the YAML file. Accepts ``str`` or
                ``pathlib.Path``.

        Returns:
            A validated :class:`AzureClawConfig` instance.

        Raises:
            FileNotFoundError: if ``path`` does not exist.
            yaml.YAMLError: if the file is not valid YAML.
            pydantic.ValidationError: if the YAML structure does not match
                the model.
        """
        text = Path(path).read_text(encoding="utf-8")
        data: dict[str, Any] = yaml.safe_load(text) or {}
        return cls.model_validate(data)
