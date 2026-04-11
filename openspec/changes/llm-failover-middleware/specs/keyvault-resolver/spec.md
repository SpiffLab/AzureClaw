## ADDED Requirements

### Requirement: KeyVaultClientLike Protocol
The package SHALL expose `azureclaw.azure.keyvault.KeyVaultClientLike` as a `typing.Protocol` (runtime-checkable) declaring a single method: `get_secret(self, name: str) -> str`. Every concrete Key Vault adapter (the in-memory stub, the real `SecretClient` wrapper) implements this Protocol.

#### Scenario: Protocol is reachable
- **WHEN** a contributor runs `python -c "from azureclaw.azure.keyvault import KeyVaultClientLike; print(KeyVaultClientLike)"`
- **THEN** the import succeeds without raising

#### Scenario: Protocol enforces the get_secret signature
- **WHEN** a class with a `get_secret(name: str) -> str` method is checked against the Protocol via `isinstance`
- **THEN** the check returns True

### Requirement: In-memory stub Key Vault client for local mode
The package SHALL expose a private class `_LocalStubKeyVaultClient` returned by `build_keyvault_client(...)` when `environment == "local"` (or when `vault_uri` is `None`). The stub holds an in-memory `dict[str, str]` of secrets and serves them via `get_secret`. Missing secrets SHALL raise `KeyError` with a clear message naming the missing secret.

#### Scenario: Stub returns seeded secrets
- **WHEN** `_LocalStubKeyVaultClient(secrets={"foo": "bar"}).get_secret("foo")` is called
- **THEN** the result is `"bar"`

#### Scenario: Missing secret raises KeyError
- **WHEN** `_LocalStubKeyVaultClient().get_secret("nope")` is called
- **THEN** a `KeyError` is raised with a message that names `"nope"`

### Requirement: Real Key Vault client wrapper
The package SHALL expose a private class `_SecretClientAdapter` that wraps `azure.keyvault.secrets.SecretClient`. Calling `get_secret(name)` SHALL invoke the wrapped client and return `secret.value` as a string. The class is constructed only by `build_keyvault_client` when `environment in ("dev", "prod")` AND `vault_uri` is non-empty.

#### Scenario: Adapter returns the .value string from the SDK response
- **WHEN** the wrapped `SecretClient.get_secret(name)` returns an object whose `.value` is `"resolved-secret"`
- **THEN** `_SecretClientAdapter(...).get_secret(name)` returns `"resolved-secret"`

### Requirement: Key Vault client factory
The package SHALL expose `build_keyvault_client(vault_uri: str | None, environment: str, credential) -> KeyVaultClientLike`. When `environment == "local"` OR `vault_uri is None`, it returns a `_LocalStubKeyVaultClient`. Otherwise it lazy-imports `azure.keyvault.secrets.SecretClient` and returns a `_SecretClientAdapter` wrapping a real `SecretClient(vault_url=vault_uri, credential=credential)`.

#### Scenario: Local environment returns the stub
- **WHEN** `build_keyvault_client(vault_uri="https://kv.vault.azure.net/", environment="local", credential=...)` is called
- **THEN** the returned object is a `_LocalStubKeyVaultClient`
- **AND** no `azure.keyvault.secrets` import has occurred

#### Scenario: Missing vault_uri returns the stub regardless of environment
- **WHEN** `build_keyvault_client(vault_uri=None, environment="dev", credential=...)` is called
- **THEN** the returned object is a `_LocalStubKeyVaultClient`

#### Scenario: Dev environment with vault_uri returns the real adapter
- **WHEN** `build_keyvault_client(vault_uri="https://kv.vault.azure.net/", environment="dev", credential=DefaultAzureCredential())` is called
- **THEN** the returned object is a `_SecretClientAdapter`
- **AND** the wrapped `SecretClient` is constructed with `vault_url="https://kv.vault.azure.net/"`

### Requirement: resolve_kv_pointer pure helper
The package SHALL expose `resolve_kv_pointer(value: str | None, kv_client: KeyVaultClientLike) -> str | None`:
- If `value` is `None`, return `None`
- If `value` does not start with the literal prefix `"@kv:"`, return `value` unchanged
- Otherwise strip the `"@kv:"` prefix and return `kv_client.get_secret(<rest>)`

The helper SHALL NOT swallow `KeyError` or any other exception raised by the Key Vault client; callers decide how to handle resolution failures.

#### Scenario: None passes through
- **WHEN** `resolve_kv_pointer(None, _LocalStubKeyVaultClient())` is called
- **THEN** the result is `None`

#### Scenario: Plain literals pass through unchanged
- **WHEN** `resolve_kv_pointer("plain-literal-value", _LocalStubKeyVaultClient())` is called
- **THEN** the result is `"plain-literal-value"`

#### Scenario: @kv: pointer is resolved against the client
- **WHEN** `resolve_kv_pointer("@kv:my-secret", _LocalStubKeyVaultClient(secrets={"my-secret": "shhh"}))` is called
- **THEN** the result is `"shhh"`

#### Scenario: Resolution failure propagates
- **WHEN** `resolve_kv_pointer("@kv:missing", _LocalStubKeyVaultClient())` is called
- **THEN** a `KeyError` is raised; the helper does not return `None` or swallow the error

#### Scenario: An empty string is treated as a literal
- **WHEN** `resolve_kv_pointer("", _LocalStubKeyVaultClient())` is called
- **THEN** the result is `""` and no Key Vault call is made
