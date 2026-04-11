## ADDED Requirements

### Requirement: Lifespan builds and exposes a Key Vault client
The gateway lifespan SHALL build a `KeyVaultClientLike` instance via `build_keyvault_client(...)` at startup and SHALL stash it on `app.state.kv_client`. The client is constructed with `vault_uri=None` (and therefore returns the in-memory stub) until a future change adds a `key_vault.uri` field to the AzureClawConfig schema.

#### Scenario: app.state.kv_client is set after startup
- **WHEN** the gateway is entered via `TestClient(create_app(config))`
- **THEN** `app.state.kv_client` is an instance of a class that satisfies the `KeyVaultClientLike` Protocol

#### Scenario: setup_observability receives the lifespan's kv_client
- **WHEN** the gateway lifespan is monkey-patched to record the arguments passed to `setup_observability`
- **THEN** the recorded `kv_client` argument is the same instance now stashed on `app.state.kv_client`
