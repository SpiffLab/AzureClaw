"""Azure Key Vault resolver for ``@kv:`` config pointers.

Every secret-bearing field in ``config.yaml`` (Anthropic API key, Discord
bot token, App Insights connection string, ...) supports a literal value
*or* an ``@kv:secret-name`` pointer that the gateway resolves at startup
through Azure Key Vault. The resolver lives here so every consumer
(observability, the LLM provider factory, future channel adapters) shares
the same convention without coupling to the Azure SDK.

Three pieces:

- :class:`KeyVaultClientLike` — a tiny Protocol with one method,
  ``get_secret(name) -> str``. Two implementations:

  - :class:`_LocalStubKeyVaultClient` — in-memory dict, used for
    ``environment="local"`` and unit tests. No network call.
  - :class:`_SecretClientAdapter` — wraps
    :class:`azure.keyvault.secrets.SecretClient` so the public surface
    stays the simple Protocol shape.

- :func:`build_keyvault_client` — factory that returns the right
  implementation based on environment + vault URI.

- :func:`resolve_kv_pointer` — the pure helper. Pass any string in,
  get back the string unchanged unless it starts with ``@kv:``, in
  which case it strips the prefix and asks the client for the secret.

The lazy import of ``azure.keyvault.secrets`` inside
:func:`build_keyvault_client` keeps the local-test path hermetic — code
that uses only the stub never imports the SDK or its transitive deps.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class KeyVaultClientLike(Protocol):
    """Minimal Key Vault client surface used by AzureClaw."""

    def get_secret(self, name: str) -> str: ...


class _LocalStubKeyVaultClient:
    """In-memory Key Vault stub for ``environment="local"`` and tests.

    Holds a ``dict[str, str]`` of secrets. Calls to :meth:`get_secret`
    raise :class:`KeyError` for missing entries so misconfiguration is
    visible at the call site rather than silently producing ``None``.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets: dict[str, str] = dict(secrets) if secrets else {}

    def get_secret(self, name: str) -> str:
        try:
            return self._secrets[name]
        except KeyError as exc:
            raise KeyError(f"secret {name!r} not found in local stub Key Vault") from exc


class _SecretClientAdapter:
    """Adapter wrapping :class:`azure.keyvault.secrets.SecretClient`."""

    def __init__(self, secret_client: Any) -> None:
        self._client = secret_client

    def get_secret(self, name: str) -> str:
        secret = self._client.get_secret(name)
        # azure-keyvault-secrets returns KeyVaultSecret objects whose
        # ``.value`` is the secret string. The cast keeps pyright happy.
        return str(secret.value)


def build_keyvault_client(
    vault_uri: str | None,
    environment: str,
    credential: Any,
) -> KeyVaultClientLike:
    """Return a Key Vault client appropriate for ``environment``.

    Args:
        vault_uri: The Key Vault URL (``https://<name>.vault.azure.net/``)
            or ``None`` if no vault is configured yet.
        environment: One of ``"local"``, ``"dev"``, ``"prod"``.
        credential: An Azure ``TokenCredential``-like object. Ignored for
            the stub branch.

    Returns:
        A :class:`KeyVaultClientLike`. The local stub for
        ``environment == "local"`` or when ``vault_uri`` is ``None``;
        a real :class:`_SecretClientAdapter` otherwise.
    """
    if environment == "local" or vault_uri is None:
        return _LocalStubKeyVaultClient()

    # Lazy import so the local-only path never pulls in the Azure SDK.
    from azure.keyvault.secrets import SecretClient

    return _SecretClientAdapter(SecretClient(vault_url=vault_uri, credential=credential))


_KV_PREFIX = "@kv:"


def resolve_kv_pointer(value: str | None, kv_client: KeyVaultClientLike) -> str | None:
    """Resolve a ``@kv:`` pointer through ``kv_client``.

    Pure helper. ``None`` passes through. Strings that do not start
    with ``@kv:`` pass through unchanged. Strings that do start with
    ``@kv:`` have the prefix stripped and the remainder is passed to
    ``kv_client.get_secret``. Resolution failures are NOT swallowed —
    callers decide how to handle them.

    Args:
        value: The raw config string. ``None`` is a passthrough.
        kv_client: Anything implementing :class:`KeyVaultClientLike`.

    Returns:
        The resolved value, or the original value if no resolution
        was needed, or ``None`` if the input was ``None``.
    """
    if value is None or not value.startswith(_KV_PREFIX):
        return value
    secret_name = value[len(_KV_PREFIX) :]
    return kv_client.get_secret(secret_name)
