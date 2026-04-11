"""Tests for ``azureclaw.observability.setup_observability``.

Every test is hermetic: no real Application Insights connection string
is exercised, no outbound HTTP call is made, and the module-level
``_setup_called`` guard is reset between tests so each test sees a
fresh state.
"""

from __future__ import annotations

from typing import Any

import pytest

import azureclaw
from azureclaw import AzureClawConfig, setup_observability
from azureclaw.azure.keyvault import _LocalStubKeyVaultClient  # pyright: ignore[reportPrivateUsage]
from azureclaw.config import ObservabilityConfig


@pytest.fixture(autouse=True)
def reset_setup_guard() -> None:
    """Reset the module-level idempotency guard before each test."""
    import azureclaw.observability as obs_mod

    obs_mod._setup_called = False  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def patched_otel(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Replace the lazy-imported OTel functions with stub recorders.

    Returns a dict whose values are call-record lists, one per stubbed
    function. Tests inspect the lists to verify which branch ran.
    """
    calls: dict[str, list[Any]] = {
        "configure_otel_providers": [],
        "enable_instrumentation": [],
        "configure_azure_monitor": [],
    }

    def fake_configure_otel_providers(**kwargs: Any) -> None:
        calls["configure_otel_providers"].append(kwargs)

    def fake_enable_instrumentation(**kwargs: Any) -> None:
        calls["enable_instrumentation"].append(kwargs)

    def fake_configure_azure_monitor(**kwargs: Any) -> None:
        calls["configure_azure_monitor"].append(kwargs)

    # Patch the functions at the source modules so the lazy imports
    # inside setup_observability resolve to the stubs.
    import agent_framework.observability as af_obs

    monkeypatch.setattr(af_obs, "configure_otel_providers", fake_configure_otel_providers)
    monkeypatch.setattr(af_obs, "enable_instrumentation", fake_enable_instrumentation)

    import azure.monitor.opentelemetry as amo

    monkeypatch.setattr(amo, "configure_azure_monitor", fake_configure_azure_monitor)

    return calls


# ─────────────────────────────────────────────────────────────────────────
# Re-export
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.local
def test_setup_observability_is_re_exported() -> None:
    """The `setup_observability` symbol is reachable from azureclaw root."""
    assert hasattr(azureclaw, "setup_observability")
    assert azureclaw.setup_observability is setup_observability
    assert "setup_observability" in azureclaw.__all__


# ─────────────────────────────────────────────────────────────────────────
# Branch 1 — disabled
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.local
def test_disabled_config_calls_no_otel_function(patched_otel: dict[str, list[Any]]) -> None:
    cfg = AzureClawConfig(
        environment="dev",
        observability=ObservabilityConfig(enabled=False),
    )

    setup_observability(cfg)

    assert patched_otel["configure_otel_providers"] == []
    assert patched_otel["enable_instrumentation"] == []
    assert patched_otel["configure_azure_monitor"] == []


# ─────────────────────────────────────────────────────────────────────────
# Branch 2 — Azure Monitor
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.local
def test_real_connection_string_in_prod_wires_azure_monitor(
    patched_otel: dict[str, list[Any]],
) -> None:
    real_cs = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://westus2-0.in.applicationinsights.azure.com/"
    )
    cfg = AzureClawConfig(
        environment="prod",
        observability=ObservabilityConfig(enabled=True, app_insights_connection_string=real_cs),
    )

    setup_observability(cfg)

    assert len(patched_otel["configure_azure_monitor"]) == 1
    assert patched_otel["configure_azure_monitor"][0] == {"connection_string": real_cs}
    assert len(patched_otel["enable_instrumentation"]) == 1
    # The local-mode all-in-one helper must NOT be called when we go via
    # configure_azure_monitor.
    assert patched_otel["configure_otel_providers"] == []


# ─────────────────────────────────────────────────────────────────────────
# Branch 3 — local / fallback
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.local
def test_local_environment_uses_console_exporter(
    patched_otel: dict[str, list[Any]],
) -> None:
    cfg = AzureClawConfig(environment="local")

    setup_observability(cfg)

    assert len(patched_otel["configure_otel_providers"]) == 1
    assert patched_otel["configure_otel_providers"][0] == {"enable_console_exporters": True}
    assert patched_otel["configure_azure_monitor"] == []
    assert patched_otel["enable_instrumentation"] == []


@pytest.mark.local
def test_missing_connection_string_in_dev_falls_back_to_console(
    patched_otel: dict[str, list[Any]],
) -> None:
    cfg = AzureClawConfig(
        environment="dev",
        observability=ObservabilityConfig(enabled=True, app_insights_connection_string=None),
    )

    setup_observability(cfg)

    assert len(patched_otel["configure_otel_providers"]) == 1
    assert patched_otel["configure_azure_monitor"] == []
    assert patched_otel["enable_instrumentation"] == []


@pytest.mark.local
def test_kv_placeholder_in_dev_falls_back_to_console(
    patched_otel: dict[str, list[Any]],
) -> None:
    cfg = AzureClawConfig(
        environment="dev",
        observability=ObservabilityConfig(
            enabled=True,
            app_insights_connection_string="@kv:app-insights-connection-string",
        ),
    )

    setup_observability(cfg)

    assert len(patched_otel["configure_otel_providers"]) == 1
    assert patched_otel["configure_azure_monitor"] == []


# ─────────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.local
def test_setup_observability_is_idempotent(
    patched_otel: dict[str, list[Any]],
) -> None:
    cfg = AzureClawConfig(environment="local")

    setup_observability(cfg)
    setup_observability(cfg)
    setup_observability(cfg)

    # configure_otel_providers should be called exactly once across the
    # three setup_observability invocations.
    assert len(patched_otel["configure_otel_providers"]) == 1


@pytest.mark.local
def test_idempotency_holds_across_config_changes(
    patched_otel: dict[str, list[Any]],
) -> None:
    """Once initialized, switching configs is a no-op (the second call
    does NOT re-wire the pipeline)."""
    local_cfg = AzureClawConfig(environment="local")
    real_cs = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://westus2-0.in.applicationinsights.azure.com/"
    )
    prod_cfg = AzureClawConfig(
        environment="prod",
        observability=ObservabilityConfig(enabled=True, app_insights_connection_string=real_cs),
    )

    setup_observability(local_cfg)
    setup_observability(prod_cfg)

    # The first call took the local branch. The second call hit the
    # idempotency guard and did NOT take the Azure Monitor branch.
    assert len(patched_otel["configure_otel_providers"]) == 1
    assert patched_otel["configure_azure_monitor"] == []
    assert patched_otel["enable_instrumentation"] == []


# ─────────────────────────────────────────────────────────────────────────
# Key Vault @kv: resolution (added by llm-failover-middleware, change #6)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.local
def test_kv_pointer_in_dev_with_populated_kv_takes_azure_monitor_branch(
    patched_otel: dict[str, list[Any]],
) -> None:
    real_cs = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://westus2-0.in.applicationinsights.azure.com/"
    )
    kv = _LocalStubKeyVaultClient(secrets={"app-insights-connection-string": real_cs})
    cfg = AzureClawConfig(
        environment="dev",
        observability=ObservabilityConfig(
            enabled=True,
            app_insights_connection_string="@kv:app-insights-connection-string",
        ),
    )

    setup_observability(cfg, kv_client=kv)

    # The resolved string takes the Azure Monitor branch.
    assert len(patched_otel["configure_azure_monitor"]) == 1
    assert patched_otel["configure_azure_monitor"][0] == {"connection_string": real_cs}
    assert len(patched_otel["enable_instrumentation"]) == 1
    assert patched_otel["configure_otel_providers"] == []


@pytest.mark.local
def test_kv_pointer_resolution_failure_falls_back_to_console(
    patched_otel: dict[str, list[Any]],
) -> None:
    """A KV miss must NOT crash the gateway; it falls back to console."""
    kv = _LocalStubKeyVaultClient()  # empty — secret missing
    cfg = AzureClawConfig(
        environment="dev",
        observability=ObservabilityConfig(
            enabled=True,
            app_insights_connection_string="@kv:app-insights-connection-string",
        ),
    )

    setup_observability(cfg, kv_client=kv)  # MUST NOT raise

    assert len(patched_otel["configure_otel_providers"]) == 1
    assert patched_otel["configure_azure_monitor"] == []


@pytest.mark.local
def test_kv_pointer_in_local_mode_is_not_resolved_even_with_kv_client(
    patched_otel: dict[str, list[Any]],
) -> None:
    """Local mode is hermetic by contract — never call KV even when populated."""
    real_cs = "InstrumentationKey=...;IngestionEndpoint=https://example/"
    kv = _LocalStubKeyVaultClient(secrets={"app-insights-connection-string": real_cs})
    cfg = AzureClawConfig(
        environment="local",
        observability=ObservabilityConfig(
            enabled=True,
            app_insights_connection_string="@kv:app-insights-connection-string",
        ),
    )

    setup_observability(cfg, kv_client=kv)

    # Local takes the console branch unconditionally.
    assert len(patched_otel["configure_otel_providers"]) == 1
    assert patched_otel["configure_azure_monitor"] == []
