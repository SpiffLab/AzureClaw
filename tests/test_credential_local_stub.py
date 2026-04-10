"""Tests for the ``local`` branch of ``build_credential``.

The contract is that the local fallback runs without any network call,
without any environment variables, and without ever importing
``azure.identity``.
"""

from __future__ import annotations

import sys

import pytest

from azureclaw.azure.credential import (
    TokenCredentialLike,
    _LocalStubCredential,  # pyright: ignore[reportPrivateUsage]
    build_credential,
)


@pytest.mark.local
def test_build_credential_local_returns_stub() -> None:
    cred = build_credential("local")

    assert isinstance(cred, _LocalStubCredential)
    assert isinstance(cred, TokenCredentialLike)


@pytest.mark.local
def test_local_stub_get_token_returns_non_empty_token() -> None:
    cred = build_credential("local")
    token = cred.get_token("https://example.com/.default")

    assert token.token != ""
    assert isinstance(token.token, str)
    assert isinstance(token.expires_on, int)


@pytest.mark.local
def test_local_path_does_not_import_azure_identity() -> None:
    """The local credential code path must not transitively pull in
    ``azure.identity``. If a contributor accidentally moves the lazy
    import to module top, this test fails immediately.
    """
    # Drop any cached references so we observe a fresh import.
    for mod in list(sys.modules):
        if mod == "azure.identity" or mod.startswith("azure.identity."):
            del sys.modules[mod]

    # Re-import the credential module via importlib to force the lazy
    # behavior to be exercised by a fresh module load.
    import importlib

    import azureclaw.azure.credential as credential_mod

    importlib.reload(credential_mod)
    cred = credential_mod.build_credential("local")
    cred.get_token("https://example.com/.default")

    assert "azure.identity" not in sys.modules


@pytest.mark.local
def test_unknown_environment_raises() -> None:
    with pytest.raises(ValueError, match="Unknown environment"):
        build_credential("staging")
