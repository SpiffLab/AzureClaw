## 1. Dependencies

- [ ] 1.1 Add `fastapi>=0.115,<1` to `pyproject.toml` `[project] dependencies`
- [ ] 1.2 Add `uvicorn[standard]>=0.32,<1` to `[project] dependencies`
- [ ] 1.3 Add `httpx>=0.28,<1` to `[project] dependencies` (needed by `fastapi.testclient` for the test suite)
- [ ] 1.4 Run `uv sync --extra dev` and confirm `uv.lock` is refreshed

## 2. Envelope types

- [ ] 2.1 Create `src/azureclaw/gateway/__init__.py` (empty subpackage marker + docstring)
- [ ] 2.2 Create `src/azureclaw/gateway/envelope.py` with Pydantic v2 models `ChannelMessage`, `AgentEvent`, `ApprovalRequest`
- [ ] 2.3 `ChannelMessage`: fields `channel: str`, `session_id: str`, `user_id: str`, `text: str`, `attachments: list[dict[str, Any]] = []`, `metadata: dict[str, Any] = {}`, `timestamp: datetime = Field(default_factory=utcnow)`
- [ ] 2.4 `AgentEvent`: fields `event_type: Literal["text_delta", "tool_call", "tool_result", "approval_request", "completed"]`, `channel: str`, `session_id: str`, `payload: dict[str, Any] = {}`, `timestamp: datetime = Field(default_factory=utcnow)`
- [ ] 2.5 `ApprovalRequest`: fields `approval_id: str = Field(default_factory=lambda: str(uuid4()))`, `tool: str`, `arguments: dict[str, Any] = {}`, `session_id: str`, `channel: str`, `requested_at: datetime = Field(default_factory=utcnow)`
- [ ] 2.6 Every model: `model_config = ConfigDict(extra="forbid")` so stray fields raise at validation time

## 3. GatewayHub

- [ ] 3.1 Create `src/azureclaw/gateway/hub.py` with class `GatewayHub`
- [ ] 3.2 Constructor: initialize `_inbound_subscribers: list[InboundCallback]` and `_outbound_subscribers: dict[str, list[OutboundCallback]]`
- [ ] 3.3 `async def publish_inbound(self, message: ChannelMessage) -> None`: iterate subscribers, call each, wrap each call in try/except + logger.exception + continue
- [ ] 3.4 `async def publish_outbound(self, event: AgentEvent) -> None`: look up by `event.channel`, iterate those subscribers with the same try/except/continue; debug log if no subscribers
- [ ] 3.5 `def subscribe_inbound(self, callback)`: append to list
- [ ] 3.6 `def subscribe_outbound(self, channel: str, callback)`: append to the channel's list (creating it if needed)
- [ ] 3.7 Type aliases `InboundCallback = Callable[[ChannelMessage], Awaitable[None]]` and `OutboundCallback = Callable[[AgentEvent], Awaitable[None]]`

## 4. FastAPI app

- [ ] 4.1 Create `src/azureclaw/gateway/routes.py` with a `router = APIRouter()` that declares `GET /healthz` returning `{"status": "ok", "package": "azureclaw", "version": azureclaw.__version__}`
- [ ] 4.2 Create `src/azureclaw/gateway/app.py` with `create_app(config: AzureClawConfig) -> FastAPI`
- [ ] 4.3 Implement the FastAPI lifespan as an `@asynccontextmanager` that calls `setup_observability(config)` at startup, creates a `GatewayHub`, attaches it to `app.state.hub`, yields, and cleans up on shutdown (no-op for now)
- [ ] 4.4 `create_app` includes `routes.router`
- [ ] 4.5 `get_app() -> FastAPI` reads `os.environ.get("AZURECLAW_CONFIG", "config.yaml")`, loads via `AzureClawConfig.from_yaml`, returns `create_app(config)`
- [ ] 4.6 Re-export `create_app` from `azureclaw.gateway.__init__` and from `azureclaw.__init__`

## 5. ChannelAdapter Protocol + in-process adapter

- [ ] 5.1 Create `src/azureclaw/adapters/__init__.py` (empty subpackage marker)
- [ ] 5.2 Create `src/azureclaw/adapters/base.py` with `@runtime_checkable` Protocol `ChannelAdapter` declaring `name`, `start`, `stop`, `send`, `render_approval`, and `router: APIRouter | None`
- [ ] 5.3 Create `src/azureclaw/adapters/inproc_test_adapter.py` with `InProcTestAdapter` implementing the Protocol
- [ ] 5.4 `InProcTestAdapter.__init__`: initialize `received: list[AgentEvent] = []`, `_hub: GatewayHub | None = None`, `router: APIRouter | None = None`
- [ ] 5.5 `async def start(hub)`: store hub, `hub.subscribe_outbound("inproc-test", self._on_outbound)`
- [ ] 5.6 `async def _on_outbound(event)`: append to `received`
- [ ] 5.7 `async def stop()`: no-op
- [ ] 5.8 `async def send(event)`: append to `received` (same as `_on_outbound` but callable directly)
- [ ] 5.9 `async def render_approval(request)`: append a synthetic `AgentEvent` with `event_type="approval_request"` and the approval id in the payload
- [ ] 5.10 `async def simulate_inbound(text, session_id="test-session")`: construct a `ChannelMessage` and call `self._hub.publish_inbound(msg)`

## 6. Package re-exports

- [ ] 6.1 Update `src/azureclaw/__init__.py` to import and re-export `create_app`, `GatewayHub`, `ChannelMessage`, `AgentEvent`, `ApprovalRequest`, `ChannelAdapter` alongside the existing `AzureClawConfig` and `setup_observability`
- [ ] 6.2 Update `__all__` with the new symbols

## 7. Tests

- [ ] 7.1 Create `tests/test_envelope.py` with `local`-marked tests: ChannelMessage round-trips through JSON; AgentEvent accepts all five event types and rejects unknown ones; ApprovalRequest has a UUID by default
- [ ] 7.2 Create `tests/test_hub.py` with `local`-marked tests: inbound fan-out, outbound channel routing, no-subscriber outbound is a no-op, raising subscriber does not break fan-out
- [ ] 7.3 Create `tests/test_gateway_app.py` with `local`-marked tests: `create_app` returns a FastAPI instance, `TestClient` lifespan calls `setup_observability` exactly once, `/healthz` returns 200 with the documented JSON shape
- [ ] 7.4 Create `tests/test_inproc_adapter.py` with `local`-marked tests: `simulate_inbound` triggers inbound subscribers, outbound events land in `received`, end-to-end echo round-trip works

## 8. Runbook

- [ ] 8.1 Create `docs/runbooks/local-gateway.md` with the `uv run uvicorn azureclaw.gateway.app:get_app --factory --reload --port 18789` command, the `AZURECLAW_CONFIG` env-var override, and a `curl http://localhost:18789/healthz` example

## 9. Verification

- [ ] 9.1 Run `uv sync --extra dev`
- [ ] 9.2 Run `uv run pytest -m local -v` — confirm all existing 17 tests plus the new gateway tests pass
- [ ] 9.3 Run `uv run ruff check src tests` — clean
- [ ] 9.4 Run `uv run ruff format --check src tests` — clean
- [ ] 9.5 Run `uv run pyright src tests` — 0 errors
- [ ] 9.6 Run `uv run uvicorn azureclaw.gateway.app:get_app --factory --port 18789` and confirm `/healthz` returns 200 (smoke — not part of CI)
- [ ] 9.7 Run `npx -y @fission-ai/openspec validate gateway-and-webhooks` — clean
- [ ] 9.8 Run `bicep build infra/main.bicep --stdout > /dev/null` — sanity check that the infra didn't regress

## 10. Commit and PR

- [ ] 10.1 Commit (1) — OpenSpec artifacts only — `spec: gateway-and-webhooks — FastAPI gateway + hub + in-process test adapter`
- [ ] 10.2 Commit (2) — implementation — `feat: gateway-and-webhooks implementation`
- [ ] 10.3 Push `feature/gateway-and-webhooks` to origin
- [ ] 10.4 Open PR against `develop` via `gh pr create`
- [ ] 10.5 Watch CI; merge when all gates are green
