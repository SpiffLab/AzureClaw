"""Unified credential factory for every Azure-touching module in AzureClaw.

The single entry point is :func:`build_credential`. It returns a
``DefaultAzureCredential`` for the ``dev`` and ``prod`` environments and a
no-op stub for ``local``. The stub satisfies the structural protocol
:class:`TokenCredentialLike` defined below — that protocol is intentionally
minimal so we can avoid importing ``azure.identity`` on the local-only test
path. Tests for the local fallback therefore run in environments where
``azure-identity`` is not installed at all.

Why a structural protocol instead of ``azure.core.credentials.TokenCredential``?

The local fallback exists so contributors and CI can validate the
orchestrator/middleware/memory paths without an Azure subscription. Importing
``azure.identity`` (which transitively imports ``azure.core``) at module top
would force every local-marker test to install the Azure identity stack for
no benefit. The lazy import inside the ``dev`` / ``prod`` branch keeps the
local path hermetic.

Future changes that need a richer credential surface (token caching,
chained credentials, federated credentials for CI) can either widen this
factory or add a sibling factory under ``azureclaw.azure``. The contract
is "the caller gets something with ``get_token``" — that is the only
guarantee.
"""

from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable


@runtime_checkable
class TokenLike(Protocol):
    """Minimal token shape — matches ``azure.core.credentials.AccessToken``."""

    token: str
    expires_on: int


@runtime_checkable
class TokenCredentialLike(Protocol):
    """Minimal credential shape used by AzureClaw.

    Matches the surface of ``azure.core.credentials.TokenCredential``
    closely enough for the call sites we need but stays import-free.
    """

    def get_token(self, *scopes: str, **kwargs: Any) -> TokenLike: ...


class _LocalStubToken:
    """Stub access token returned by :class:`_LocalStubCredential`."""

    def __init__(self) -> None:
        self.token: str = "stub-token-not-for-production"
        self.expires_on: int = 0


class _LocalStubCredential:
    """No-op credential used by ``environment="local"``.

    Never opens a network connection. Returns a deterministic stub token
    so call sites that just need *something* can run in unit tests.
    """

    def get_token(self, *scopes: str, **kwargs: Any) -> TokenLike:  # noqa: ARG002
        return _LocalStubToken()


def build_credential(environment: str = "dev") -> TokenCredentialLike:
    """Return the credential to use for the given environment.

    Args:
        environment: One of ``"local"``, ``"dev"``, or ``"prod"``.
            ``"local"`` returns a hermetic stub. ``"dev"`` and ``"prod"``
            return ``azure.identity.DefaultAzureCredential``.

    Returns:
        An object satisfying :class:`TokenCredentialLike`.

    Raises:
        ValueError: if ``environment`` is not one of the recognised values.
    """
    if environment == "local":
        return _LocalStubCredential()
    if environment in ("dev", "prod"):
        # Lazy import so the local path does not transitively load
        # azure.identity (and through it azure.core, msal, etc.).
        from azure.identity import DefaultAzureCredential

        # `DefaultAzureCredential` satisfies our structural protocol at
        # runtime; the cast tells pyright to trust the structural match
        # since `azure.core.credentials.AccessToken` is a dataclass with
        # the same `token` / `expires_on` shape as `TokenLike`.
        return cast(TokenCredentialLike, DefaultAzureCredential())
    raise ValueError(
        f"Unknown environment {environment!r}; expected one of 'local', 'dev', 'prod'."
    )
