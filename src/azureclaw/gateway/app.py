"""AzureClaw gateway application factory.

Two entry points:

- :func:`create_app` — the pure factory every test and every caller
  uses. Takes a validated :class:`AzureClawConfig`, returns a fresh
  :class:`fastapi.FastAPI` instance whose lifespan calls
  :func:`azureclaw.setup_observability` exactly once at startup.
- :func:`get_app` — the ``uvicorn ... --factory`` entry point. Reads
  the YAML config path from the ``AZURECLAW_CONFIG`` environment
  variable (defaulting to ``config.yaml``) and hands off to
  :func:`create_app`.

Canonical local-run command::

    uv run uvicorn azureclaw.gateway.app:get_app --factory --reload --port 18789

The lifespan also attaches a shared :class:`GatewayHub` to
``app.state.hub`` so future webhook routes can reach it via
``request.app.state.hub``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from azureclaw.config import AzureClawConfig
from azureclaw.gateway.hub import GatewayHub
from azureclaw.gateway.routes import router as core_router
from azureclaw.observability import setup_observability


def create_app(config: AzureClawConfig) -> FastAPI:
    """Build a fresh :class:`FastAPI` instance for the given config.

    The returned app's lifespan will call
    :func:`azureclaw.setup_observability` with ``config`` at startup
    and attach a new :class:`GatewayHub` to ``app.state.hub``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_observability(config)
        app.state.hub = GatewayHub()
        app.state.config = config
        try:
            yield
        finally:
            # No cleanup required yet; channel adapters will register
            # their own stop() hooks in future changes.
            pass

    app = FastAPI(
        title="AzureClaw Gateway",
        description="Azure-native Microsoft Agent Framework re-imagining of OpenClaw.",
        version="0.0.0",
        lifespan=lifespan,
    )
    app.include_router(core_router)
    return app


def get_app() -> FastAPI:
    """uvicorn factory entry point.

    Invoked via ``uvicorn azureclaw.gateway.app:get_app --factory``.
    Reads the config path from the ``AZURECLAW_CONFIG`` env var,
    defaulting to ``config.yaml`` in the current working directory.
    """
    config_path = Path(os.environ.get("AZURECLAW_CONFIG", "config.yaml"))
    config = AzureClawConfig.from_yaml(config_path)
    return create_app(config)
