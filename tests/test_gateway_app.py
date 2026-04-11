"""Tests for ``azureclaw.gateway.app.create_app``."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import azureclaw
from azureclaw import AzureClawConfig, GatewayHub, create_app
from azureclaw.azure.keyvault import KeyVaultClientLike


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
    the config it was created with AND the kv_client it built."""
    # Reset the idempotency guard so this test is independent of prior ones.
    import azureclaw.observability as obs_mod

    obs_mod._setup_called = False  # pyright: ignore[reportPrivateUsage]

    calls: list[tuple[AzureClawConfig, Any]] = []

    def fake_setup(config: AzureClawConfig, kv_client: Any = None) -> None:
        calls.append((config, kv_client))

    monkeypatch.setattr("azureclaw.gateway.app.setup_observability", fake_setup)

    cfg = AzureClawConfig(environment="local")
    app = create_app(cfg)

    with TestClient(app):
        pass  # entering + exiting the context manager runs the lifespan

    assert len(calls) == 1
    assert calls[0][0] is cfg
    # The lifespan must pass the same kv_client now stashed on app.state.
    assert calls[0][1] is app.state.kv_client


@pytest.mark.local
def test_lifespan_attaches_hub_config_credential_and_kv_client_to_app_state() -> None:
    cfg = AzureClawConfig(environment="local")
    app = create_app(cfg)

    with TestClient(app):
        state: Any = app.state
        assert isinstance(state.hub, GatewayHub)
        assert state.config is cfg
        # Credential and kv_client are also reachable.
        assert state.credential is not None
        assert isinstance(state.kv_client, KeyVaultClientLike)
