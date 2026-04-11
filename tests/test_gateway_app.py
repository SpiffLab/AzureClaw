"""Tests for ``azureclaw.gateway.app.create_app``."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import azureclaw
from azureclaw import AzureClawConfig, GatewayHub, create_app


@pytest.mark.local
def test_create_app_returns_fastapi_instance() -> None:
    app = create_app(AzureClawConfig(environment="local"))
    assert isinstance(app, FastAPI)


@pytest.mark.local
def test_healthz_returns_ok_without_auth() -> None:
    app = create_app(AzureClawConfig(environment="local"))
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["package"] == "azureclaw"
    assert body["version"] == azureclaw.__version__


@pytest.mark.local
def test_lifespan_invokes_setup_observability_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The app's lifespan must call setup_observability exactly once with
    the config it was created with."""
    # Reset the idempotency guard so this test is independent of prior ones.
    import azureclaw.observability as obs_mod

    obs_mod._setup_called = False  # pyright: ignore[reportPrivateUsage]

    calls: list[AzureClawConfig] = []

    def fake_setup(config: AzureClawConfig) -> None:
        calls.append(config)

    monkeypatch.setattr("azureclaw.gateway.app.setup_observability", fake_setup)

    cfg = AzureClawConfig(environment="local")
    app = create_app(cfg)

    with TestClient(app):
        pass  # entering + exiting the context manager runs the lifespan

    assert len(calls) == 1
    assert calls[0] is cfg


@pytest.mark.local
def test_lifespan_attaches_hub_and_config_to_app_state() -> None:
    cfg = AzureClawConfig(environment="local")
    app = create_app(cfg)

    with TestClient(app):
        # After lifespan startup, app.state.hub and app.state.config exist.
        state: Any = app.state
        assert isinstance(state.hub, GatewayHub)
        assert state.config is cfg
