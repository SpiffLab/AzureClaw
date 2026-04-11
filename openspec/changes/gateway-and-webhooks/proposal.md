## Why

Every later OpenSpec change — Triage agent, failover middleware, Magentic team, every channel adapter, the on-prem connector — assumes an HTTP control plane exists. That control plane is the FastAPI gateway. Without it, there is nowhere to mount webhook routes, nowhere to wire up the startup `setup_observability(config)` call, and nowhere for the orchestrator to publish inbound messages from or subscribe to outbound events on.

This change ships the **smallest runnable gateway**: a FastAPI app with `/healthz`, a `GatewayHub` that holds the inbound-pub and outbound-subscribe-by-channel primitives, strongly-typed `ChannelMessage` / `AgentEvent` / `ApprovalRequest` envelopes, a `ChannelAdapter` Protocol, and an in-process test adapter that lets tests round-trip a synthetic message through the whole pipeline without any real channel implementation. It also wires `setup_observability(config)` into the FastAPI lifespan so startup telemetry works the moment a real deploy happens.

## What Changes

- Add runtime dependencies to `pyproject.toml`: `fastapi>=0.115,<1`, `uvicorn[standard]>=0.32,<1`, `httpx>=0.28,<1`
- Create `src/azureclaw/gateway/__init__.py` (empty subpackage marker with docstring)
- Create `src/azureclaw/gateway/envelope.py` exposing three Pydantic v2 models: `ChannelMessage` (inbound), `AgentEvent` (outbound), and `ApprovalRequest` (HITL). All three are serializable to JSON and carry timestamps + stable ids.
- Create `src/azureclaw/gateway/hub.py` exposing `GatewayHub`: an async message-routing primitive with `publish_inbound(msg)`, `publish_outbound(event)`, `subscribe_inbound(callback)`, and `subscribe_outbound(channel, callback)`. Thread-safe enough for a single-process async gateway.
- Create `src/azureclaw/gateway/app.py` exposing:
  - `create_app(config: AzureClawConfig) -> FastAPI` — the canonical factory. Builds the FastAPI app with the lifespan that calls `setup_observability(config)` at startup.
  - `get_app() -> FastAPI` — the uvicorn factory entry point that loads config from the `AZURECLAW_CONFIG` env var (default `config.yaml`). Invoked via `uvicorn azureclaw.gateway.app:get_app --factory`.
- Create `src/azureclaw/gateway/routes.py` exposing a small `APIRouter` with `/healthz`. No per-channel webhook routes in this change — each channel adapter change ships its own `APIRouter` that `create_app` mounts.
- Create `src/azureclaw/adapters/__init__.py` (empty subpackage marker)
- Create `src/azureclaw/adapters/base.py` exposing the `ChannelAdapter` Protocol: `name`, `start(hub)`, `stop()`, `send(event)`, `render_approval(request)`, optional `router: APIRouter | None`
- Create `src/azureclaw/adapters/inproc_test_adapter.py` exposing `InProcTestAdapter` — a hermetic adapter used only by tests. Implements the Protocol, holds a list of received `AgentEvent`s, and exposes `simulate_inbound(text, session_id)` so tests can inject a `ChannelMessage` into the hub.
- Re-export `create_app`, `GatewayHub`, `ChannelMessage`, `AgentEvent`, `ApprovalRequest`, and `ChannelAdapter` from `azureclaw.__init__`
- Create `docs/runbooks/local-gateway.md` documenting how to boot the gateway locally via `uv run uvicorn azureclaw.gateway.app:get_app --factory --reload --port 18789`
- Add `tests/test_envelope.py`, `tests/test_hub.py`, `tests/test_gateway_app.py`, and `tests/test_inproc_adapter.py` covering every spec scenario

**Non-goals (explicitly not in this change):**
- Real Entra ID validation middleware. APIM fronts the gateway in production and handles Entra validation at the edge; the gateway itself gets an authenticated header. The middleware lands with the change that wires APIM (`a2a-interop-apim`, #15). Until then the `/healthz` route is unauthenticated.
- Any per-channel webhook route (Discord / Telegram / WhatsApp / Teams / iMessage). Each channel adapter change contributes its own `APIRouter`.
- Any agent, Triage router, Magentic team, or real subscriber to `hub.publish_inbound`. The orchestrator lands with `triage-and-typed-routing` (#7).
- Session persistence. The hub is in-process-only in this change; Cosmos-backed session state lands in `memory-cosmos-aisearch` (#9).
- Any approval queue delivery. HITL routing via Service Bus lands in `approval-loop-servicebus` (#10).
- WebSocket streaming back to in-browser test clients (WebChat was removed from the MVP scope; the `InProcTestAdapter` replaces it for tests).

## Capabilities

### New Capabilities

- `gateway`: the FastAPI control plane, the `GatewayHub` primitive, the envelope types, the `ChannelAdapter` Protocol, and the in-process test adapter. Every later change either mounts routes on the gateway app, subscribes to hub events, or implements the Protocol.

### Modified Capabilities

- `package-skeleton`: the `azureclaw` package gains six new public re-exports (`create_app`, `GatewayHub`, `ChannelMessage`, `AgentEvent`, `ApprovalRequest`, `ChannelAdapter`)
- `observability`: `setup_observability` is now called automatically from the FastAPI lifespan, not just by test fixtures. A new scenario covers the lifespan wiring.

## Impact

- **Affected systems:** local working tree only; no Azure resource is touched; CI gains a test suite that boots the FastAPI app via `fastapi.testclient.TestClient`
- **Affected dependencies:** `pyproject.toml` gains `fastapi`, `uvicorn[standard]`, `httpx`. `uv.lock` grows by ~12 packages (starlette, anyio, h11, httpcore, httptools, watchfiles, websockets, annotated-doc, click, + the three above).
- **Affected APIs:** introduces `azureclaw.create_app`, `azureclaw.GatewayHub`, `azureclaw.ChannelMessage`, `azureclaw.AgentEvent`, `azureclaw.ApprovalRequest`, `azureclaw.ChannelAdapter` as public symbols. Also `uvicorn azureclaw.gateway.app:get_app --factory` becomes the canonical runnable command.
- **Affected docs:** `docs/runbooks/local-gateway.md` is new.
- **Reversibility:** fully reversible — revert the PR. No external state.
