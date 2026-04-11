## ADDED Requirements

### Requirement: Single observability entry point
The package SHALL expose `azureclaw.setup_observability(config: AzureClawConfig) -> None` as the single function every AzureClaw process calls at startup to wire the OpenTelemetry pipeline. The function SHALL be re-exported from `azureclaw.__init__` so callers can `from azureclaw import setup_observability`.

#### Scenario: Function is importable from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import setup_observability"`
- **THEN** the import succeeds without raising

#### Scenario: Function accepts a validated AzureClawConfig
- **WHEN** the function is called with an instance of `AzureClawConfig`
- **THEN** it returns `None` (no exceptions raised on any of the three branches: disabled, local, Azure Monitor)

### Requirement: Disabled mode is a clean no-op
When `config.observability.enabled` is `False`, `setup_observability` SHALL log a single informational message ("observability disabled") and return without invoking any OpenTelemetry function or any Azure SDK function.

#### Scenario: Disabled config does not call OTel providers
- **WHEN** `setup_observability` is called with a config whose `observability.enabled = False`
- **THEN** `agent_framework.observability.configure_otel_providers` is NOT called
- **AND** `azure.monitor.opentelemetry.configure_azure_monitor` is NOT called
- **AND** the function returns within milliseconds

### Requirement: Local / fallback mode uses the console exporter
When `config.environment == "local"`, OR when `config.observability.app_insights_connection_string` is `None`, empty, or a `@kv:` placeholder string, `setup_observability` SHALL configure the OpenTelemetry pipeline using `agent_framework.observability.configure_otel_providers(enable_console_exporters=True)` and SHALL NOT attempt to call `configure_azure_monitor`.

#### Scenario: Local environment routes to console exporter
- **WHEN** `setup_observability` is called with `config.environment = "local"`
- **THEN** `agent_framework.observability.configure_otel_providers` is called with `enable_console_exporters=True`
- **AND** `azure.monitor.opentelemetry.configure_azure_monitor` is NOT called

#### Scenario: Missing connection string falls back to console exporter
- **WHEN** `setup_observability` is called with `config.environment = "dev"` and `config.observability.app_insights_connection_string = None`
- **THEN** the function logs a warning that no connection string is configured
- **AND** `configure_otel_providers(enable_console_exporters=True)` is called
- **AND** `configure_azure_monitor` is NOT called

#### Scenario: @kv: placeholder falls back to console exporter
- **WHEN** `setup_observability` is called with `config.observability.app_insights_connection_string = "@kv:app-insights-connection-string"`
- **THEN** the function logs a warning that the placeholder cannot be resolved until `llm-failover-middleware` lands
- **AND** `configure_otel_providers(enable_console_exporters=True)` is called
- **AND** `configure_azure_monitor` is NOT called

### Requirement: Azure Monitor mode wires Application Insights and MAF instrumentation
When `config.environment` is `"dev"` or `"prod"` AND `config.observability.app_insights_connection_string` is a non-empty string that does not begin with `@kv:`, `setup_observability` SHALL call `azure.monitor.opentelemetry.configure_azure_monitor(connection_string=...)` followed by `agent_framework.observability.enable_instrumentation()`.

#### Scenario: Real connection string wires Azure Monitor
- **WHEN** `setup_observability` is called with `config.environment = "prod"` and `config.observability.app_insights_connection_string = "InstrumentationKey=...;IngestionEndpoint=..."`
- **THEN** `azure.monitor.opentelemetry.configure_azure_monitor` is called with that exact string
- **AND** `agent_framework.observability.enable_instrumentation` is called immediately after

### Requirement: Idempotent initialization
`setup_observability` SHALL guard against double initialization. The first call SHALL execute the configured branch. Every subsequent call (regardless of whether the config changed) SHALL log a single debug message and return without re-invoking any OTel or Azure SDK function.

#### Scenario: Calling setup_observability twice does not raise
- **WHEN** `setup_observability(config)` is called twice in the same process
- **THEN** neither call raises
- **AND** the second call does not invoke any OpenTelemetry function

#### Scenario: Idempotency holds across config changes
- **WHEN** `setup_observability` is called with a local-mode config, then called again with a dev-mode config
- **THEN** the second call does NOT switch the pipeline; it logs the debug message and returns
- **AND** the original local-mode pipeline remains in place

### Requirement: KQL runbook documents the audit log queries
The repository SHALL contain `docs/runbooks/observability.md` with at minimum these KQL query examples ready to paste into the Application Insights workspace, scoped to the AzureClaw audit log: spans by `session_id`, spans by `channel`, tool-call P50/P95 latency, provider failover events, approval request lifecycle, errors by agent name, and top expensive tool calls.

#### Scenario: Runbook exists at the documented path
- **WHEN** a contributor opens `docs/runbooks/observability.md`
- **THEN** the file exists and contains at least 7 distinct fenced ```kql``` blocks
- **AND** each query references either `dependencies`, `requests`, `traces`, or `customEvents` (the App Insights tables that auto-instrumentation populates)

## MODIFIED Requirements

### Requirement: Importable azureclaw package
The repository SHALL contain an installable Python package named `azureclaw` rooted at `src/azureclaw/` that exposes a `__version__` string, the `AzureClawConfig` model, and the `setup_observability` function. All three SHALL be importable from a fresh `uv sync` of `pyproject.toml`.

#### Scenario: Package imports cleanly after uv sync
- **WHEN** a contributor runs `uv sync` followed by `uv run python -c "import azureclaw; print(azureclaw.__version__)"`
- **THEN** the command exits 0 and prints a non-empty version string

#### Scenario: Editable install registers the package
- **WHEN** a contributor runs `uv pip install -e .`
- **THEN** `python -c "import azureclaw"` succeeds in any working directory

#### Scenario: setup_observability is re-exported from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import setup_observability; print(setup_observability.__name__)"`
- **THEN** the command exits 0 and prints `setup_observability`
