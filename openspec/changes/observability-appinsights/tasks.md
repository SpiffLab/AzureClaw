## 1. Dependencies

- [ ] 1.1 Add `agent-framework-core>=1.0,<2` to `pyproject.toml` `[project] dependencies`
- [ ] 1.2 Add `azure-monitor-opentelemetry>=1.8,<2` to `[project] dependencies`
- [ ] 1.3 Run `uv sync --extra dev` to update `uv.lock` with the new transitive packages

## 2. Observability module

- [ ] 2.1 Create `src/azureclaw/observability.py` with a module docstring explaining the three branches and the idempotency contract
- [ ] 2.2 Add a module-level `_setup_called: bool = False` guard
- [ ] 2.3 Implement `setup_observability(config: AzureClawConfig) -> None` with three explicit branches: disabled, local/fallback, Azure Monitor
- [ ] 2.4 Lazy-import `agent_framework.observability` and `azure.monitor.opentelemetry` inside the branches that need them (not at module top)
- [ ] 2.5 Use Python's stdlib `logging` for the module logger; do not introduce a custom logger framework
- [ ] 2.6 Re-export `setup_observability` from `src/azureclaw/__init__.py` and add it to `__all__`

## 3. Tests

- [ ] 3.1 Create `tests/test_observability.py` with the `local` pytest marker on every test
- [ ] 3.2 Add a fixture that resets `_setup_called` to `False` before each test (so idempotency tests are independent)
- [ ] 3.3 Test: `setup_observability` is importable from `azureclaw` package root
- [ ] 3.4 Test: disabled config does not call `configure_otel_providers` or `configure_azure_monitor` (via `monkeypatch.setattr`)
- [ ] 3.5 Test: `environment="local"` calls `configure_otel_providers(enable_console_exporters=True)`
- [ ] 3.6 Test: missing connection string in `dev` mode falls back to console
- [ ] 3.7 Test: `@kv:` placeholder in `dev` mode falls back to console
- [ ] 3.8 Test: real connection string in `prod` mode calls `configure_azure_monitor` then `enable_instrumentation`
- [ ] 3.9 Test: calling `setup_observability` twice does not call any OTel function on the second call
- [ ] 3.10 Test: idempotency holds even when the second call's config has a different environment

## 4. KQL runbook

- [ ] 4.1 Delete `docs/.gitkeep`
- [ ] 4.2 Create `docs/runbooks/observability.md` with at least 7 KQL queries: spans by `session_id`, spans by `channel`, tool-call P50/P95 latency, provider failover events, approval request lifecycle, errors by agent name, top expensive tool calls
- [ ] 4.3 Add a one-paragraph "How to use" section explaining where to paste the queries and which Application Insights workspace to scope them to

## 5. Verification

- [ ] 5.1 Run `uv sync --extra dev` and confirm the new dependencies install
- [ ] 5.2 Run `uv run pytest -m local -v` and confirm every test passes (including the 9 existing tests + 8 new observability tests)
- [ ] 5.3 Run `uv run ruff check src tests` and confirm clean
- [ ] 5.4 Run `uv run ruff format --check src tests` and confirm clean
- [ ] 5.5 Run `uv run pyright src tests` and confirm clean
- [ ] 5.6 Run `npx -y @fission-ai/openspec validate observability-appinsights` and confirm clean
- [ ] 5.7 Confirm Bicep files still compile (`bicep build infra/main.bicep --stdout > /dev/null`) — sanity check; no infra files change in this PR

## 6. Commit and PR

- [ ] 6.1 Commit (1) — OpenSpec artifacts only — `spec: observability-appinsights — MAF + Application Insights wiring`
- [ ] 6.2 Commit (2) — implementation — `feat: observability-appinsights implementation`
- [ ] 6.3 Push `feature/observability-appinsights` to origin
- [ ] 6.4 Open PR against `develop` via `gh pr create`
- [ ] 6.5 Watch CI; merge when all four gates are green
