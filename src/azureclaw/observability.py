"""Single observability entry point for AzureClaw.

The whole pipeline is configured by one function — :func:`setup_observability` —
that every entry point calls at startup. Three disjoint branches:

1. **Disabled** — `config.observability.enabled is False`. Logs and returns.
2. **Local / fallback** — `config.environment == "local"`, OR the connection
   string is missing / empty / starts with the ``@kv:`` placeholder prefix.
   Calls :func:`agent_framework.observability.configure_otel_providers`
   with ``enable_console_exporters=True``. Spans go to stdout. Hermetic;
   no network call.
3. **Azure Monitor** — `config.environment` is ``"dev"`` or ``"prod"`` AND
   the connection string is a real (non-empty, non-``@kv:``) string.
   Calls :func:`azure.monitor.opentelemetry.configure_azure_monitor`
   then :func:`agent_framework.observability.enable_instrumentation`.
   Spans, metrics, and logs flow to Application Insights.

The function is **idempotent**. A module-level guard prevents double
initialization — re-entrant fixtures and signal handlers can call it
more than once safely.

The lazy imports inside each branch keep import-time side effects
minimal: a process that calls ``setup_observability`` with a disabled
config never imports the OTel or Azure Monitor packages.

``@kv:`` connection strings degrade gracefully to console with a warning.
The Key Vault resolver lands in ``llm-failover-middleware`` (OpenSpec
change #6); until then this fall-through is the documented contract.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azureclaw.config import AzureClawConfig

logger = logging.getLogger(__name__)

# Module-level guard against double initialization. OTel providers are
# global mutable state — calling configure_*_providers twice produces
# duplicate registrations whose later spans go nowhere. The guard is
# reset between tests by a fixture in tests/test_observability.py.
_setup_called: bool = False


def setup_observability(config: AzureClawConfig) -> None:
    """Configure the OpenTelemetry pipeline for the current process.

    Idempotent. Calling more than once is a no-op + debug log.

    Args:
        config: A validated :class:`azureclaw.config.AzureClawConfig`.
            The function reads `config.environment` and
            `config.observability.app_insights_connection_string` to
            decide which branch to take.
    """
    global _setup_called

    if _setup_called:
        logger.debug("setup_observability called more than once; ignoring re-init")
        return

    obs_cfg = config.observability

    # ─── Branch 1: disabled ───────────────────────────────────────────
    if not obs_cfg.enabled:
        logger.info("observability disabled in config")
        _setup_called = True
        return

    connection_string = obs_cfg.app_insights_connection_string
    has_real_connection_string = (
        connection_string is not None
        and connection_string != ""
        and not connection_string.startswith("@kv:")
    )

    # ─── Branch 2: Azure Monitor ──────────────────────────────────────
    # Only when environment is dev/prod AND we have a real (non-placeholder)
    # connection string. Anything else falls through to console.
    if config.environment in ("dev", "prod") and has_real_connection_string:
        from agent_framework.observability import enable_instrumentation

        # azure-monitor-opentelemetry's public function uses
        # `**kwargs: Any` so pyright reports its type as partially
        # unknown. The behaviour is well-defined and the kwarg name
        # `connection_string` is documented. Suppress on import only.
        from azure.monitor.opentelemetry import (
            configure_azure_monitor,  # pyright: ignore[reportUnknownVariableType]
        )

        # configure_azure_monitor registers Azure Monitor exporters as
        # the default OTel providers globally. We then enable MAF's
        # auto-instrumentation on top, so agent.run() / tool calls /
        # workflow supersteps emit spans through the Azure Monitor
        # pipeline alongside Azure SDK + HTTP spans.
        configure_azure_monitor(connection_string=connection_string)
        enable_instrumentation()
        logger.info(
            "observability wired to Application Insights (environment=%s)",
            config.environment,
        )
        _setup_called = True
        return

    # ─── Branch 3: local / fallback ───────────────────────────────────
    # configure_otel_providers is the all-in-one MAF function — it
    # registers tracer/meter/logger providers AND enables MAF
    # instrumentation. With enable_console_exporters=True the spans
    # land in stdout, which pytest captures and the operator can
    # inspect during local-dev runs.
    from agent_framework.observability import configure_otel_providers

    if connection_string is not None and connection_string.startswith("@kv:"):
        logger.warning(
            "App Insights connection string is the placeholder %r; "
            "Key Vault resolution lands in llm-failover-middleware. "
            "Falling back to the console exporter.",
            connection_string,
        )
    elif config.environment in ("dev", "prod"):
        logger.warning(
            "environment=%s but no app_insights_connection_string is configured; "
            "falling back to the console exporter.",
            config.environment,
        )
    else:
        logger.info("observability wired to console exporter (environment=local)")

    configure_otel_providers(enable_console_exporters=True)
    _setup_called = True
