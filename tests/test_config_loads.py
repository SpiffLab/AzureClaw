"""Tests proving ``AzureClawConfig.from_yaml`` parses ``config.example.yaml``
without validation errors and exposes the documented fields.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from azureclaw import AzureClawConfig

# config.example.yaml lives at the repository root, two levels above tests/.
EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "config.example.yaml"


@pytest.mark.local
def test_config_example_yaml_parses() -> None:
    cfg = AzureClawConfig.from_yaml(EXAMPLE_CONFIG)

    assert cfg.environment == "dev"
    assert len(cfg.providers) == 3
    assert {p.kind for p in cfg.providers} == {"foundry", "anthropic", "ollama"}


@pytest.mark.local
def test_config_kv_pointer_preserved_as_literal() -> None:
    """``@kv:`` secret pointers must survive parsing as plain strings.

    Resolution against Azure Key Vault is the responsibility of a later
    OpenSpec change (``llm-failover-middleware``); the bootstrap-skeleton
    only requires that the literal string is preserved.
    """
    cfg = AzureClawConfig.from_yaml(EXAMPLE_CONFIG)

    anthropic = next(p for p in cfg.providers if p.kind == "anthropic")
    assert anthropic.api_key == "@kv:anthropic-api-key"


@pytest.mark.local
def test_config_defaults_when_optional_sections_missing(tmp_path: Path) -> None:
    """A YAML file with only ``environment:`` set should still validate, with
    every optional section using its declared default."""
    minimal = tmp_path / "minimal.yaml"
    minimal.write_text("environment: local\n", encoding="utf-8")

    cfg = AzureClawConfig.from_yaml(minimal)

    assert cfg.environment == "local"
    assert cfg.providers == []
    assert cfg.embeddings is None
    assert cfg.memory.backend == "sqlite"
    assert cfg.observability.enabled is True
    assert cfg.hybrid.enabled is False
    assert cfg.a2a.enabled is False
