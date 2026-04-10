"""AzureClaw — an Azure-native Microsoft Agent Framework re-imagining of OpenClaw.

This package is intentionally minimal in the bootstrap-skeleton change. The
real surface (gateway, orchestrator, adapters, tools, middleware, memory)
lands incrementally through subsequent OpenSpec changes under
``openspec/changes/``.
"""

from azureclaw.config import AzureClawConfig

__version__ = "0.0.0"

__all__ = ["AzureClawConfig", "__version__"]
