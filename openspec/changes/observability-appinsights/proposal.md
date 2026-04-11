## Why

Every later OpenSpec change — Triage agent, failover middleware, Magentic team, channel adapters, Cosmos memory — emits OpenTelemetry spans through Microsoft Agent Framework. Those spans need a destination. This change wires the OpenTelemetry pipeline once, in one place, so every later change just gets observability for free without bespoke logging code.

This is also the change that **introduces Microsoft Agent Framework as a runtime dependency**. AzureClaw is built on MAF; until now we've only had the foundational config + credential plumbing. Pulling MAF in here keeps the dependency footprint honest: the first change to need MAF is the one that adds it.

## What Changes

- Add `agent-framework-core` (the MAF base SDK; ~30 transitive packages — much smaller than the umbrella `agent-framework` which pulls in 150+) to `pyproject.toml` runtime dependencies
- Add `azure-monitor-opentelemetry` to `pyproject.toml` runtime dependencies
- Create `src/azureclaw/observability.py` exposing `setup_observability(config: AzureClawConfig) -> None` that:
  - **Disabled mode** (`config.observability.enabled is False`): logs and returns without touching OTel
  - **Local / fallback mode** (`environment == "local"`, OR `app_insights_connection_string` is None / empty / starts with `@kv:`): calls `agent_framework.observability.configure_otel_providers(enable_console_exporters=True)`. Spans go to stdout. Works without any Azure credential and without a real connection string.
  - **Azure Monitor mode** (real connection string AND `environment in ("dev", "prod")`): calls `azure.monitor.opentelemetry.configure_azure_monitor(connection_string=...)` then `agent_framework.observability.enable_instrumentation()`. Spans, metrics, and logs flow to Application Insights.
  - **Idempotent**: a module-level guard prevents double initialization (calling twice is a no-op + debug log). Critical for re-entrant test fixtures and re-arming during a workflow restart.
- Re-export `setup_observability` from `azureclaw.__init__` so `from azureclaw import setup_observability` works
- Create `docs/runbooks/observability.md` with KQL query examples for the audit log: spans by `session_id`, spans by `channel`, tool-call latency P50/P95, provider failover events, approval request lifecycle, errors by agent name, top expensive tool calls
- Remove `docs/.gitkeep` (this change is the first to put a real file under `docs/`)
- Add `tests/test_observability.py` covering disabled, local, `@kv:` placeholder fall-through, idempotency, and the `setup_observability` re-export

**Non-goals (explicitly not in this change):**
- Resolving `@kv:` connection strings against Azure Key Vault. The Key Vault resolver lands in `llm-failover-middleware` (#6). Until then, an `@kv:` connection string falls through to console exporter with a warning log.
- Adding any custom span attributes (`session_id`, `channel`, `entra_oid`). The custom audit middleware lands in a later change.
- Adding any agent, tool, workflow, or channel adapter that *emits* spans. This change wires the pipeline; later changes feed into it.
- Calling `configure_azure_monitor` from any test (would require a real connection string). The Azure Monitor branch is reachable via mocks.

## Capabilities

### New Capabilities

- `observability`: the unified OpenTelemetry pipeline for AzureClaw, plus the contract that every agent/tool/workflow span flows through Application Insights in production and through the console exporter in local/dev tests

### Modified Capabilities

- `package-skeleton`: the `azureclaw` package gains a second public re-export, `setup_observability`

## Impact

- **Affected systems:** local working tree only; no Azure resource is touched (no connection to Application Insights is opened by tests)
- **Affected dependencies:** `pyproject.toml` gains `agent-framework-core` and `azure-monitor-opentelemetry` as runtime dependencies. `uv.lock` grows substantially (30 net new packages including OTel, MAF core, opentelemetry-instrumentation-* and azure-core-tracing-opentelemetry).
- **Affected APIs:** introduces `azureclaw.setup_observability` as a public function alongside `azureclaw.AzureClawConfig`
- **Affected docs:** `docs/runbooks/observability.md` is created (the first real doc in `docs/`)
- **Reversibility:** fully reversible — revert the PR, the lockfile shrinks back, no Azure state existed to touch
