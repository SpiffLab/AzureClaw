"""Tests for ``azureclaw.azure.keyvault``."""

from __future__ import annotations

import pytest

from azureclaw.azure.keyvault import (
    KeyVaultClientLike,
    _LocalStubKeyVaultClient,  # pyright: ignore[reportPrivateUsage]
    build_keyvault_client,
    resolve_kv_pointer,
)

# ─── Protocol + stub ─────────────────────────────────────────────────────


@pytest.mark.local
def test_protocol_is_satisfied_by_stub() -> None:
    stub = _LocalStubKeyVaultClient()
    assert isinstance(stub, KeyVaultClientLike)


@pytest.mark.local
def test_stub_returns_seeded_secrets() -> None:
    stub = _LocalStubKeyVaultClient(secrets={"foo": "bar", "baz": "qux"})
    assert stub.get_secret("foo") == "bar"
    assert stub.get_secret("baz") == "qux"


@pytest.mark.local
def test_stub_raises_keyerror_on_missing_secret() -> None:
    stub = _LocalStubKeyVaultClient()
    with pytest.raises(KeyError, match="missing"):
        stub.get_secret("missing")


# ─── Factory ─────────────────────────────────────────────────────────────


@pytest.mark.local
def test_factory_returns_stub_in_local_mode() -> None:
    client = build_keyvault_client(
        vault_uri="https://kv.vault.azure.net/",
        environment="local",
        credential=None,
    )
    assert isinstance(client, _LocalStubKeyVaultClient)


@pytest.mark.local
def test_factory_returns_stub_when_vault_uri_is_none() -> None:
    client = build_keyvault_client(vault_uri=None, environment="dev", credential=None)
    assert isinstance(client, _LocalStubKeyVaultClient)


@pytest.mark.local
def test_factory_does_not_import_azure_keyvault_in_local_mode() -> None:
    """Local-only path must not pull in the Azure SDK at runtime."""
    import sys

    # Force a fresh import of the module to observe what gets loaded
    # under our feet during build_keyvault_client.
    for mod in list(sys.modules):
        if mod.startswith("azure.keyvault.secrets"):
            del sys.modules[mod]

    build_keyvault_client(
        vault_uri="https://kv.vault.azure.net/",
        environment="local",
        credential=None,
    )

    assert "azure.keyvault.secrets" not in sys.modules


# ─── resolve_kv_pointer ──────────────────────────────────────────────────


@pytest.mark.local
def test_resolve_none_returns_none() -> None:
    assert resolve_kv_pointer(None, _LocalStubKeyVaultClient()) is None


@pytest.mark.local
def test_resolve_plain_literal_passes_through_unchanged() -> None:
    assert resolve_kv_pointer("plain-value", _LocalStubKeyVaultClient()) == "plain-value"


@pytest.mark.local
def test_resolve_empty_string_passes_through_unchanged() -> None:
    assert resolve_kv_pointer("", _LocalStubKeyVaultClient()) == ""


@pytest.mark.local
def test_resolve_kv_pointer_returns_secret_value() -> None:
    stub = _LocalStubKeyVaultClient(secrets={"my-secret": "shhh"})
    assert resolve_kv_pointer("@kv:my-secret", stub) == "shhh"


@pytest.mark.local
def test_resolve_kv_pointer_propagates_keyerror_on_missing_secret() -> None:
    stub = _LocalStubKeyVaultClient()
    with pytest.raises(KeyError, match="missing"):
        resolve_kv_pointer("@kv:missing", stub)
