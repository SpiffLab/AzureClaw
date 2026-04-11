## Context

Four changes in, AzureClaw has a config model, a credential factory, a complete Bicep blueprint, and MAF observability wiring — but no HTTP surface. Every later change assumes an HTTP control plane exists: `triage-and-typed-routing` subscribes to the hub's inbound events, `magentic-research-team` ships a browser MCP sidecar hanging off the ACA gateway app, every channel adapter mounts a webhook router, and `approval-loop-servicebus` exposes `/approvals` routes. This change is the seam all of those land on.

The hard discipline here is to ship the *smallest* runnable gateway. No real authentication (APIM handles Entra validation at the edge in production and the gateway trusts APIM-injected headers), no channel-specific webhook routes (each adapter contributes its own `APIRouter`), no agent, no orchestrator, no Cosmos-backed session store. Just:

- A FastAPI app built by a pure factory
- A hub primitive for inbound fan-out and outbound channel routing
- Strongly-typed envelopes so every boundary has a schema
- A Protocol that future adapters implement
- An in-process test adapter that makes hermetic integration tests possible (there is no WebChat in the MVP)
- The lifespan wiring that makes `setup_observability` load-bearing at startup

## Goals / Non-Goals

**Goals:**

- `uv run uvicorn azureclaw.gateway.app:get_app --factory --reload --port 18789` boots the gateway against `config.example.yaml` without any Azure credential. `/healthz` responds 200.
- `create_app(config)` is a pure factory — tests construct it with a test config, hit it via `TestClient`, assert on the behaviour.
- The `GatewayHub` primitive is small, fully typed, and independently testable. No global state.
- The first real integration test in the repo: `test_inproc_adapter_round_trip` registers an echo subscriber on the hub, simulates an inbound message through the in-process adapter, asserts the echo event landed on the adapter's `received` list. End-to-end pub/sub exercised without any real channel.
- The `setup_observability` call happens exactly once per app, at startup, via the FastAPI lifespan. Idempotent against the module-level guard that already exists.

**Non-Goals:**

- Any agent / orchestrator / Triage / Magentic / tool / channel adapter beyond the in-process test one. All of those are owned by later changes.
- Real Entra ID validation middleware. APIM handles Entra at the edge in production; the gateway trusts APIM-injected headers. The header-trust middleware lands with `a2a-interop-apim` (#15) so it can be tested against real APIM config.
- Any webhook route for Discord / Telegram / WhatsApp / Teams / iMessage. Each channel adapter change contributes its own `APIRouter`.
- A WebSocket surface for streaming `AgentEvent`s to an in-browser client. WebChat was dropped from the MVP; the in-process test adapter replaces it for tests.
- Cosmos-backed session storage (`memory-cosmos-aisearch`), approval queue delivery via Service Bus (`approval-loop-servicebus`), or any persistence at all. Everything is in-process for this change.
- CLI entry point (`python -m azureclaw`). The `uvicorn ... --factory` invocation is the canonical local-run command. A CLI `__main__.py` can land in a tiny follow-up if needed.

## Decisions

### Decision: `create_app(config)` is a pure factory; `get_app()` is the uvicorn entry point

**Why:** Testability. A module-level `app = create_app(_load_config())` at the top of `app.py` runs at import time — which means every test that imports `azureclaw.gateway.app` triggers YAML loading and observability setup. That is exactly the footgun that makes FastAPI test suites flaky and slow. Splitting into two functions gives us:

- `create_app(config)` for tests — call it with whatever config the test needs, no I/O at import
- `get_app()` for uvicorn — loads the config and calls `create_app` under the `--factory` flag

uvicorn's `--factory` flag is explicitly designed for this pattern and has been stable since 0.20.

**Alternatives considered:** module-level `app` variable (rejected for the reason above); construct the app inside `__main__.py` (rejected: breaks `uvicorn azureclaw.gateway.app:app` as a discoverable entry point).

### Decision: `GatewayHub` uses in-memory async fan-out, not a broker

**Why:** This change ships a single-process gateway. Multi-worker fan-out, durable delivery, and backpressure are problems we don't have yet. A hub that's a few dicts of async callbacks is ~50 lines and has zero operational dependencies. The broker-backed version (Service Bus for approvals, Redis for cross-worker fan-out) lands with the changes that actually need them.

The hub's public surface (`publish_inbound`, `publish_outbound`, `subscribe_inbound`, `subscribe_outbound`) is designed to be stable across any future broker swap — later changes can replace the internals without touching call sites.

**Alternatives considered:** Service Bus from day one (rejected: adds a durable external dependency to every local test); Python's `asyncio.Queue` (rejected: queues are point-to-point but we need fan-out); third-party pub/sub library like `aioreactive` (rejected: overkill for 50 lines of routing).

### Decision: Envelopes are Pydantic v2 models, not dataclasses

**Why:** We already use Pydantic v2 for `AzureClawConfig`. Every boundary in the codebase wants the same validation + JSON round-trip story. Dataclasses don't give us `model_validate` or `model_dump(mode="json")` for free. And FastAPI's type-driven routing integrates natively with Pydantic models for request/response validation — when webhook routes land in later changes, they can bind to these envelope types directly.

`ChannelMessage` uses `Literal`-typed `channel` field? **No** — the set of channel names grows with every adapter change. We keep `channel: str` and let each adapter be responsible for using its own identifier consistently. The alternative would require a discriminated union that every new change has to extend.

**Alternatives considered:** `attrs` classes + `cattrs` (rejected: smaller ecosystem, worse FastAPI integration); `dataclasses.dataclass` (rejected: no built-in validation); TypedDict (rejected: no runtime checks).

### Decision: `subscribe_inbound` takes a single `Callable[[ChannelMessage], Awaitable[None]]`, not a filter

**Why:** The orchestrator is the only real inbound subscriber in the final system — Triage consumes every inbound message and decides what to do with it. Per-channel filtering happens inside the orchestrator, not in the hub. Adding a filter parameter would bloat the API with no real benefit, and later changes that want per-channel routing can use `msg.channel` in their own callback.

**Alternatives considered:** `subscribe_inbound(callback, channel_filter: str | None = None)` (rejected: premature abstraction; no known caller needs it).

### Decision: `subscribe_outbound` IS per-channel, because adapters are inherently per-channel

**Why:** The inverse of the previous decision. Outbound events route to exactly one channel — the channel whose adapter is rendering them. If we had a global outbound subscriber, every adapter would filter on `event.channel` and drop events that aren't theirs. That's pure boilerplate. Keying subscriptions by channel at the hub moves the filter into the one place that has context to do it correctly.

### Decision: A raising inbound/outbound subscriber does not break the fan-out

**Why:** If one adapter's `send` raises (transient network error, rate limit, platform outage), other adapters should still render the same event. The hub wraps each subscriber invocation in a `try: ... except: logger.exception(...); continue` block so one bad actor can't take down the fan-out. This is the standard pub/sub contract.

**Alternatives considered:** fail-fast (rejected: one Discord outage shouldn't break Telegram); re-raise after logging (rejected: same); require subscribers to handle their own errors (rejected: easy to forget; the hub is the enforcement point).

### Decision: Lifespan calls `setup_observability` exactly once, trusting the existing module-level guard

**Why:** `setup_observability` is already idempotent (OpenSpec change #4 landed that). The lifespan just calls it unconditionally at startup. If the app is torn down and recreated in the same process (e.g., for a hot-reload), the second call hits the guard and no-ops. If the test fixture resets the guard, both calls run independently — which is what tests want.

### Decision: No authentication on `/healthz`

**Why:** Health probes are hit by the Azure Container Apps ingress, by Kubernetes-style liveness checks, and by monitoring tools that don't carry Entra tokens. `/healthz` is the one route that MUST be reachable without auth. Everything else (once auth lands) is protected.

### Decision: The in-process test adapter lives in `src/`, not `tests/`

**Why:** It's a reusable fixture. Future changes that want end-to-end orchestrator tests will import it. Putting it under `src/azureclaw/adapters/inproc_test_adapter.py` makes it discoverable alongside the real adapters and available to downstream consumers. Tests that use it import normally.

The naming (`inproc_test_adapter`) makes its purpose unmistakable — no one will accidentally ship it as a production adapter.

**Alternatives considered:** `tests/fixtures/inproc_adapter.py` (rejected: not reusable outside tests); `src/azureclaw/adapters/test/` (rejected: looks like a test directory inside src).

## Risks / Trade-offs

- **Risk:** Pydantic v2 `Literal` types for `AgentEvent.event_type` lock in the set of event types. Adding a new type later is a breaking change to the model. → **Mitigation:** the initial set (`text_delta`, `tool_call`, `tool_result`, `approval_request`, `completed`) covers every MAF-emitted event type we know of. Adding a new one is a deliberate decision worth a spec update.

- **Risk:** The hub is in-memory, so multi-worker ACA deploys (2+ replicas) will have per-replica fan-out, and a user whose inbound lands on replica A won't see the response from replica B. → **Mitigation:** the ACA scale is set to `minReplicas: 0, maxReplicas: 3` in `containerapps.bicep`, but the MVP is expected to run at 1 replica. When multi-worker fan-out becomes a real need, we swap the hub internals to Service Bus or Redis Pub/Sub without touching the public API.

- **Risk:** FastAPI's `TestClient` uses httpx + a thread pool, which doesn't exercise the async code paths as faithfully as a real uvicorn server. → **Mitigation:** acceptable for the spec scenarios in this change (every assertion is about the `GatewayHub` and the envelope types, both of which are pure Python async). Tests that need full async fidelity can use `httpx.AsyncClient(transport=ASGITransport(app=app))`.

- **Risk:** Adding 12 new packages (fastapi + starlette + uvicorn[standard] extras) bloats the install. → **Mitigation:** acceptable; fastapi is the gateway and is foundational. Extras like `watchfiles` (for `--reload`) and `websockets` (for WebSocket support later) are pulled in by `uvicorn[standard]` and are small.

- **Risk:** `uvicorn azureclaw.gateway.app:get_app --factory` depends on `config.yaml` existing in the CWD. A contributor running the command from the wrong directory gets a confusing error. → **Mitigation:** the runbook documents the exact command with `--port 18789` and a reminder to cp `config.example.yaml config.yaml` first. The error message from `AzureClawConfig.from_yaml` is already clear (`FileNotFoundError` with the resolved path).

- **Risk:** The envelope models accept arbitrary `dict` payloads in `AgentEvent.payload` and `ChannelMessage.metadata`, which defeats some of the type safety. → **Mitigation:** the payloads have per-event-type shapes that the orchestrator knows. Tightening them to discriminated unions is a follow-up once we know the exact shapes from real usage. For now `dict[str, Any]` is honest about what's there.

- **Risk:** Pyright strict on FastAPI + Starlette can be chatty. → **Mitigation:** we already have a working pyright-strict setup from previous changes. FastAPI's type stubs are good enough in 0.115+. If a specific issue appears it gets a targeted `pyright: ignore`.

## Migration Plan

Post-merge state:

1. `src/azureclaw/gateway/` exists with four modules (`__init__`, `app`, `envelope`, `hub`, `routes`).
2. `src/azureclaw/adapters/` exists with three modules (`__init__`, `base`, `inproc_test_adapter`).
3. `pyproject.toml` declares `fastapi`, `uvicorn[standard]`, and `httpx` as runtime dependencies. `uv.lock` is refreshed.
4. The `azureclaw` package re-exports six new public symbols.
5. `docs/runbooks/local-gateway.md` explains how to boot the gateway locally.
6. `pytest -m local` passes with the existing 17 tests + ~12 new ones.
7. `uv run uvicorn azureclaw.gateway.app:get_app --factory --port 18789` boots and responds 200 to `/healthz`.

**Rollback:** revert the PR. No external state.

## Open Questions

- Should the lifespan also create and expose a shared `GatewayHub` instance as `app.state.hub` so routes can reach it via the request? **Yes, and this change does it.** The lifespan attaches `hub = GatewayHub()` to `app.state.hub` at startup so the future webhook routes can access it through `request.app.state.hub`.

- Should the hub be a singleton module-level instance instead of app-state? **No.** Module-level singletons break tests (state leaks between tests) and multi-app scenarios (multiple `create_app` calls in one process for split-brain tests). Living on `app.state` is the idiomatic FastAPI pattern.

- Should we ship a `/readyz` route in addition to `/healthz`? **Deferred.** `/healthz` is sufficient for ACA's default probe. The Kubernetes distinction between liveness and readiness only matters once we have dependencies that need time to warm up. When `memory-cosmos-aisearch` lands, `/readyz` can verify Cosmos connectivity while `/healthz` stays a pure process-alive probe.

- Should the `ChannelAdapter` Protocol be `@runtime_checkable`? **Yes.** Tests can `isinstance(adapter, ChannelAdapter)` assert which is useful for the adapter-registration machinery later. `@runtime_checkable` on a Protocol with a few simple members is cheap.
