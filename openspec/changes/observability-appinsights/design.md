## Context

AzureClaw is built on Microsoft Agent Framework. MAF auto-instruments every `agent.run()`, every tool call, every workflow superstep, and every approval request as OpenTelemetry spans. Those spans need a destination, and that destination is Application Insights in production. This change wires the pipeline once, in `src/azureclaw/observability.py`, so every later change just gets observability for free.

It is also the change that **introduces MAF as a runtime dependency** — the first one. Until now AzureClaw has had only the foundational layer (Pydantic config, hermetic credential factory, repo conventions, infra Bicep). Pulling MAF in here is the smallest scope where MAF is actually load-bearing.

A non-obvious complication: we cannot resolve `@kv:` Key Vault placeholder strings yet. The Key Vault resolver lands in `llm-failover-middleware` (#6, two changes from now). But `config.example.yaml` has already documented `app_insights_connection_string: "@kv:app-insights-connection-string"` as the production pattern. The observability function therefore needs a graceful fall-through: if the connection string is a `@kv:` placeholder, it logs a warning and uses the console exporter instead. When `llm-failover-middleware` lands, that branch gets quietly retired.

I introspected the actual MAF observability API before writing the spec. The plan document mentioned `agent_framework.observability.setup_observability(...)` — that function does not exist. The real surface is:

- `agent_framework.observability.configure_otel_providers(*, enable_console_exporters, enable_sensitive_data, exporters, views, vs_code_extension_port, env_file_path)` — sets up tracer/meter/logger providers AND enables MAF instrumentation. The "all-in-one" function for the local/console path.
- `agent_framework.observability.enable_instrumentation(*, enable_sensitive_data)` — turns on MAF auto-instrumentation only. Used after `configure_azure_monitor` because `configure_azure_monitor` registers its own providers and we just need to layer MAF spans on top.
- `azure.monitor.opentelemetry.configure_azure_monitor(**kwargs)` — the Application Insights configuration entry point. Accepts `connection_string="..."`.

Both packages installed cleanly via `uv pip install agent-framework-core azure-monitor-opentelemetry` (30 net new packages, much smaller than the umbrella `agent-framework` meta-package which would pull 150+).

## Goals / Non-Goals

**Goals:**

- A single, idempotent `setup_observability(config)` function that every entry point calls at startup.
- Three execution branches that never overlap: disabled, local/fallback, Azure Monitor.
- The local fallback runs without any Azure credential, without any real connection string, and without making any network call. Critical for `pytest -m local` and for contributors without Azure access.
- A `@kv:` placeholder in the connection string degrades gracefully to console — never crashes the gateway.
- Idempotency. Re-entrant test fixtures, workflow restarts, and signal handlers can call `setup_observability` more than once safely.
- KQL runbook with the queries an oncall would actually use during an incident.

**Non-Goals:**

- Resolving `@kv:` strings (lives in `llm-failover-middleware`).
- Custom span attributes (`session_id`, `channel`, `entra_oid`). Those attach via a custom audit middleware later.
- Any real Application Insights connection — tests cannot make outbound HTTP calls in the local marker.
- Tracing or instrumenting any other library beyond what MAF + `azure-monitor-opentelemetry` already wire automatically.
- Configuring sampling, head-based vs tail-based sampling, or any other production tuning. Defaults are sufficient for the MVP.

## Decisions

### Decision: Depend on `agent-framework-core` instead of the `agent-framework` umbrella

**Why:** The umbrella `agent-framework` package on PyPI installs **151 packages**, including every per-provider subpackage (Foundry, Claude, Anthropic, Bedrock, Cosmos, Azure AI Search, OpenAI, Mem0, Redis, …). For this change we only need the core SDK and observability. `agent-framework-core==1.0.1` is published as a separate distribution and pulls only ~30 packages including OTel and the MAF base classes.

Each later change adds the specific subpackage it needs: `llm-failover-middleware` will add `agent-framework-foundry`, `memory-cosmos-aisearch` will add `agent-framework-azure-cosmos`, etc. This keeps the dependency footprint honest and the install fast.

**Alternatives considered:** depend on the umbrella `agent-framework` (rejected: bloats install with 120+ unused packages); skip MAF entirely and roll our own observability wiring on top of raw OpenTelemetry (rejected: defeats the entire reason we picked MAF — we'd lose auto-instrumentation of `agent.run()`, tool calls, workflows).

### Decision: Three disjoint execution branches inside a single function

**Why:** "Disabled", "local/fallback", and "Azure Monitor" are conceptually different code paths with different invariants. Putting them in one function with an explicit branch chain is more readable than three separate functions with overlapping setup boilerplate. The function's body is a 25-line if/elif/else with one log line per branch.

**Alternatives considered:** one function per branch (rejected: callers would have to know which branch their config is in, defeating "one entry point"); strategy pattern with three classes (rejected: massive overkill for a 25-line function).

### Decision: `@kv:` connection strings degrade to console with a warning, not a hard error

**Why:** `config.example.yaml` ships with the connection string set to `@kv:app-insights-connection-string` as the documented production pattern. If the observability function raised on `@kv:` strings, the `bootstrap-skeleton` test that loads `config.example.yaml` would still pass (since that test doesn't call `setup_observability`), but the very first call to `setup_observability` from a real entry point would crash before MAF wiring could land. The graceful fall-through means the gateway can boot in any environment, log a clear warning, and ship spans to stdout until Key Vault is wired in `llm-failover-middleware`.

The fall-through is also what makes the function callable from a `pytest -m local` test that loads `config.example.yaml` directly without monkey-patching.

**Alternatives considered:** raise on `@kv:` (rejected: blocks bring-up); silently ignore (rejected: reviewers would not realize observability is degraded); detect by environment (`local` always uses console; `dev`/`prod` always tries Azure Monitor) (rejected: reviewers would be confused why `dev` with `@kv:` placeholder crashes vs falls through).

### Decision: Module-level boolean guard for idempotency

**Why:** OpenTelemetry providers are global mutable state. Calling `configure_otel_providers` twice in the same process registers two tracer providers, two meter providers, and two logger providers — and the second call's spans go into a void because OTel only tracks one active provider per type. The same applies to `configure_azure_monitor`.

A module-level `_setup_called: bool = False` flag is the simplest way to make the function idempotent across re-entrant fixtures, signal handlers, and worker process restarts. It's not threadsafe in the strict sense, but `setup_observability` is called from the gateway lifespan startup, which runs single-threaded.

**Alternatives considered:** `functools.lru_cache(maxsize=1)` (rejected: caches by argument hash, but `AzureClawConfig` instances aren't hashable); `threading.Lock` (rejected: not needed at startup); checking OTel's global state directly (rejected: relies on OTel internals that may change).

### Decision: KQL runbook lives under `docs/runbooks/`, not `docs/`

**Why:** Operational runbooks are a distinct kind of document from architectural docs. A `runbooks/` subdirectory creates space for the eventual `incident-response.md`, `failover-recovery.md`, `connector-onboarding.md` files without crowding the architecture docs that will land in `docs/architecture/` or sitting alongside them in confusing flat layout.

**Alternatives considered:** flat `docs/observability.md` (rejected: docs grow into a junk drawer); `docs/ops/` (rejected: less specific than `runbooks/`); inline in `README.md` (rejected: README is for marketing + getting started, not operations).

### Decision: Console exporter is enabled even in `dev` mode when the connection string is missing

**Why:** Spans should always go *somewhere*. Silently throwing away telemetry because the operator forgot to set `app_insights_connection_string` would mean a developer wonders why their MAF spans never appear. Falling back to the console exporter is loud (every span prints to stdout) and self-evidently wrong, which is exactly the right failure mode for missing config.

## Risks / Trade-offs

- **Risk:** `agent-framework-core==1.0.1` is a recent release; its API may shift between minor versions. → **Mitigation:** pin to `>=1.0,<2`. The MAF team has committed to semver for the 1.x series. If a 1.x breaking change ships, the contract is that we revert and pin the old patch.

- **Risk:** `azure-monitor-opentelemetry` versions sometimes lag MAF's OTel version requirements (the OpenTelemetry community ships breaking changes fairly often). → **Mitigation:** pin both packages without upper bounds initially; if a version conflict appears at `uv sync`, pin the offending package's range. The lockfile catches it at PR time (CI's `ci/test` job runs `uv sync --all-extras`).

- **Risk:** The console exporter is verbose. In a long-running local test suite it will print thousands of lines. → **Mitigation:** acceptable for the MVP — it's behind the `local` marker and pytest captures stdout by default. If it becomes painful, we can add a `console_fallback: bool = True` flag to `ObservabilityConfig` that defaults to true but can be disabled per environment.

- **Risk:** `configure_azure_monitor` opens a network connection at call time to the App Insights ingestion endpoint. If a test accidentally takes the Azure Monitor branch (e.g., a regression sets `environment="dev"` and a real connection string), the test would make an outbound HTTP call, which is forbidden in `local`-marked tests. → **Mitigation:** the function's branch logic is structured so that only an `environment in ("dev", "prod")` AND a real (non-empty, non-`@kv:`) connection string takes the Azure Monitor branch. Tests set `environment="local"` or use `@kv:` placeholders, both of which fall through to console. The test suite asserts this contract explicitly.

- **Risk:** Idempotency via a module-level flag is weak — `importlib.reload(observability)` resets it. → **Mitigation:** acceptable; reloading observability in production would be very deliberate and very rare. We could use OTel's internal state, but that couples us to OTel internals.

- **Risk:** Adding 30 transitive packages doubles the local-dev install size. → **Mitigation:** acceptable; MAF + OTel is the foundational dependency for everything that follows. Each later change adds 1-3 more packages, not 30.

## Migration Plan

This is greenfield code added on top of the bootstrap-skeleton. Post-merge state:

1. `src/azureclaw/observability.py` exists.
2. `azureclaw.setup_observability` is importable from the package root.
3. `pyproject.toml` declares `agent-framework-core>=1.0,<2` and `azure-monitor-opentelemetry>=1.8,<2`.
4. `uv.lock` is updated with ~30 net new packages.
5. `docs/runbooks/observability.md` exists with KQL examples.
6. `docs/.gitkeep` is removed.
7. The `local`-marker pytest suite still passes; new tests cover all five scenarios in the spec.

**Rollback:** revert the PR. The dependency tree shrinks, the observability module disappears, the package re-export goes back to just `AzureClawConfig`. No external state.

## Open Questions

- Should `setup_observability` accept `enable_sensitive_data` as a parameter that defaults to `False` and gets surfaced through `config.observability`? **Deferred:** not needed yet; `enable_sensitive_data` controls whether MAF includes prompt content in spans, which becomes a privacy decision when the first real agent lands. Easy to add as an optional kwarg without breaking callers.

- Should we add a `service.name` resource attribute via a custom resource override so App Insights' "Cloud role name" column shows `azureclaw-gateway` instead of the default? **Yes**, but deferred to the `gateway-and-webhooks` change since the gateway is the entity whose role name matters. For now the default is fine.

- Should we register a `pytest_collection_modifyitems` hook that auto-calls `setup_observability` in local mode for every test? **No**: spans would be emitted from tests that aren't even exercising MAF, polluting stdout. Tests that need spans call `setup_observability` explicitly via a fixture.
