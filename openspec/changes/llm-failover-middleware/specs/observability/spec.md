## MODIFIED Requirements

### Requirement: Single observability entry point
The package SHALL expose `azureclaw.setup_observability(config: AzureClawConfig, kv_client: KeyVaultClientLike | None = None) -> None` as the single function every AzureClaw process calls at startup to wire the OpenTelemetry pipeline. The function SHALL be re-exported from `azureclaw.__init__` so callers can `from azureclaw import setup_observability`. The FastAPI gateway's lifespan SHALL call `setup_observability` exactly once at startup, passing the Key Vault client it built so `@kv:` connection strings are resolved into real Application Insights connection strings.

#### Scenario: Function is importable from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import setup_observability"`
- **THEN** the import succeeds without raising

#### Scenario: Function accepts a validated AzureClawConfig
- **WHEN** the function is called with an instance of `AzureClawConfig`
- **THEN** it returns `None` (no exceptions raised on any of the three branches)

#### Scenario: The gateway lifespan calls setup_observability with a kv_client
- **WHEN** the gateway's FastAPI app is entered via `TestClient(create_app(config))`
- **THEN** `setup_observability` is called exactly once with the same config passed to `create_app`
- **AND** the second positional argument is the `KeyVaultClientLike` the lifespan also stashed on `app.state.kv_client`

#### Scenario: kv_client defaults to None for backward compatibility
- **WHEN** existing tests call `setup_observability(config)` with no `kv_client` argument
- **THEN** the call succeeds and follows the same fall-through behavior as before this change (no @kv: resolution)

### Requirement: @kv: placeholder is resolved when a kv_client is provided
When `setup_observability` is called with a non-None `kv_client` AND `config.observability.app_insights_connection_string` starts with the `@kv:` prefix, the function SHALL call `resolve_kv_pointer` on the connection string before evaluating the local-vs-Azure-Monitor branch. If resolution succeeds, the resolved string is treated as a real connection string. If resolution raises `KeyError` (or any other exception), the function logs a warning and falls back to the console exporter without raising.

#### Scenario: @kv: connection string in dev with a stub KV is resolved
- **WHEN** `setup_observability` is called with `environment="dev"`, `app_insights_connection_string="@kv:app-insights-connection-string"`, and a stub KV client containing `{"app-insights-connection-string": "InstrumentationKey=...;..."}`
- **THEN** `configure_azure_monitor` is called with `connection_string="InstrumentationKey=...;..."`
- **AND** `enable_instrumentation` is called immediately after

#### Scenario: @kv: connection string with KV resolution failure falls back to console
- **WHEN** `setup_observability` is called with `environment="dev"`, an `@kv:` connection string, and a stub KV client that does NOT have that secret
- **THEN** the function logs a warning that names the missing secret
- **AND** `configure_otel_providers(enable_console_exporters=True)` is called
- **AND** `configure_azure_monitor` is NOT called
- **AND** the function does NOT raise

#### Scenario: @kv: in local mode is NOT resolved, regardless of kv_client
- **WHEN** `setup_observability` is called with `environment="local"`, an `@kv:` connection string, and a stub KV client that contains the secret
- **THEN** `configure_otel_providers(enable_console_exporters=True)` is called
- **AND** `configure_azure_monitor` is NOT called
- **AND** the resolved string is NOT requested from the KV client (local mode skips resolution entirely)
