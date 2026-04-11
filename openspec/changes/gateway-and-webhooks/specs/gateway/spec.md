## ADDED Requirements

### Requirement: Envelope types are Pydantic models with stable fields
The package SHALL expose three Pydantic v2 models under `azureclaw.gateway.envelope`: `ChannelMessage` (inbound from a channel), `AgentEvent` (outbound to a channel), and `ApprovalRequest` (HITL). Every envelope type SHALL carry at minimum `channel: str`, `session_id: str`, and `timestamp: datetime`. Every type SHALL round-trip cleanly through `model_dump(mode="json")` and `model_validate(...)`.

#### Scenario: ChannelMessage round-trips through JSON
- **WHEN** a `ChannelMessage` instance is serialized via `model_dump(mode="json")` and the result is passed back through `ChannelMessage.model_validate`
- **THEN** the reconstructed instance equals the original (on every field)

#### Scenario: AgentEvent enumerates the supported event types
- **WHEN** an `AgentEvent` is constructed with `event_type="text_delta"`, `"tool_call"`, `"tool_result"`, `"approval_request"`, or `"completed"`
- **THEN** construction succeeds
- **AND** any other string value raises `pydantic.ValidationError`

#### Scenario: ApprovalRequest carries the tool name and an approval id
- **WHEN** an `ApprovalRequest` is constructed
- **THEN** it has non-empty `approval_id` (a UUID4 by default), `tool` (the function name), and `requested_at` timestamp fields

### Requirement: GatewayHub routes inbound to all subscribers and outbound by channel
The package SHALL expose `azureclaw.gateway.hub.GatewayHub` with four methods:

1. `async def publish_inbound(self, message: ChannelMessage) -> None`
2. `async def publish_outbound(self, event: AgentEvent) -> None`
3. `def subscribe_inbound(self, callback: Callable[[ChannelMessage], Awaitable[None]]) -> None`
4. `def subscribe_outbound(self, channel: str, callback: Callable[[AgentEvent], Awaitable[None]]) -> None`

Inbound messages SHALL be fanned out to every registered inbound subscriber in registration order. Outbound events SHALL be delivered only to subscribers registered for the event's exact `channel` value.

#### Scenario: publish_inbound delivers to every subscriber
- **WHEN** two inbound subscribers are registered and `publish_inbound(msg)` is called
- **THEN** both subscribers receive `msg` exactly once

#### Scenario: publish_outbound routes by channel name
- **WHEN** subscribers are registered for channels `"telegram"` and `"discord"`, and `publish_outbound(event)` is called with `event.channel == "telegram"`
- **THEN** the `"telegram"` subscriber receives the event
- **AND** the `"discord"` subscriber does NOT

#### Scenario: publish_outbound with no matching subscribers is a no-op
- **WHEN** `publish_outbound(event)` is called with a channel that has no registered subscribers
- **THEN** the call returns cleanly without raising
- **AND** emits a debug log so the dropped event is auditable

#### Scenario: A raising subscriber does not prevent other subscribers from running
- **WHEN** two subscribers are registered for the same channel and the first raises an exception
- **THEN** the exception is caught and logged
- **AND** the second subscriber still runs

### Requirement: FastAPI gateway is built via a pure factory
The package SHALL expose `azureclaw.gateway.app.create_app(config: AzureClawConfig) -> FastAPI`. Calling it SHALL return a fully configured `FastAPI` instance whose lifespan calls `azureclaw.setup_observability(config)` exactly once at startup. The function SHALL be pure — calling it twice with the same config SHALL return two independent app instances (the observability idempotency guard handles the global-state contract).

#### Scenario: create_app returns a FastAPI instance
- **WHEN** `create_app(AzureClawConfig(environment="local"))` is called
- **THEN** the return value is an instance of `fastapi.FastAPI`

#### Scenario: The app lifespan invokes setup_observability
- **WHEN** the app is entered via `with fastapi.testclient.TestClient(app):`
- **THEN** `azureclaw.setup_observability` is called exactly once with the config that `create_app` received

### Requirement: /healthz returns a stable JSON payload
The gateway SHALL expose `GET /healthz` which returns HTTP 200 with the JSON body `{"status": "ok", "package": "azureclaw", "version": "<version>"}` where `<version>` equals `azureclaw.__version__`.

#### Scenario: /healthz is reachable without authentication
- **WHEN** a test client sends `GET /healthz` with no authentication headers
- **THEN** the response status is 200
- **AND** the response body is a JSON object with `status == "ok"` and `package == "azureclaw"`

#### Scenario: /healthz reports the package version
- **WHEN** a test client sends `GET /healthz`
- **THEN** the response body's `version` field equals `azureclaw.__version__`

### Requirement: uvicorn factory entry point
The package SHALL expose `azureclaw.gateway.app.get_app() -> FastAPI` as the uvicorn factory entry point. `get_app` SHALL read the YAML config path from the environment variable `AZURECLAW_CONFIG` (defaulting to `config.yaml` relative to the current working directory), load it via `AzureClawConfig.from_yaml`, and return `create_app(config)`.

#### Scenario: get_app defaults the config path
- **WHEN** `get_app` is called with no `AZURECLAW_CONFIG` env var set and `config.yaml` exists in the CWD
- **THEN** it returns a `FastAPI` instance

#### Scenario: get_app honours AZURECLAW_CONFIG
- **WHEN** `AZURECLAW_CONFIG` is set to a custom path and that file exists
- **THEN** `get_app` loads that file and passes the resulting config to `create_app`

### Requirement: ChannelAdapter Protocol
The package SHALL expose `azureclaw.adapters.base.ChannelAdapter` as a `typing.Protocol` (runtime-checkable) with the following members:

- `name: str` — the channel identifier (`"whatsapp"`, `"telegram"`, `"discord"`, `"imessage"`, `"teams"`, `"inproc-test"`, etc.)
- `async def start(self, hub: GatewayHub) -> None` — subscribe to outbound events for `self.name` and begin listening for platform-side messages
- `async def stop(self) -> None` — graceful shutdown
- `async def send(self, event: AgentEvent) -> None` — render an `AgentEvent` into a platform-native message
- `async def render_approval(self, request: ApprovalRequest) -> None` — render an `ApprovalRequest` as a platform-native interactive prompt
- `router: APIRouter | None` — optional FastAPI router the channel adapter contributes (webhook routes); `None` for adapters that do not need HTTP ingress (e.g., Discord's gateway WebSocket)

#### Scenario: The Protocol is reachable from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import ChannelAdapter; print(ChannelAdapter.__name__)"`
- **THEN** the command exits 0 and prints `ChannelAdapter`

### Requirement: In-process test adapter for hermetic integration tests
The package SHALL expose `azureclaw.adapters.inproc_test_adapter.InProcTestAdapter` — a concrete adapter whose `name == "inproc-test"`, that subscribes to outbound events for its channel on `start(hub)`, appends received `AgentEvent`s to a public `received: list[AgentEvent]` for test inspection, and exposes `async simulate_inbound(text: str, session_id: str = "test-session") -> None` that constructs a `ChannelMessage` and calls `hub.publish_inbound(...)`.

#### Scenario: simulate_inbound triggers hub subscribers
- **WHEN** an `InProcTestAdapter` is started against a hub, an inbound subscriber is registered, and `simulate_inbound("hello")` is called
- **THEN** the inbound subscriber receives a `ChannelMessage` with `text == "hello"` and `channel == "inproc-test"`

#### Scenario: Outbound events published to the adapter's channel land in `received`
- **WHEN** an `InProcTestAdapter` is started against a hub and `hub.publish_outbound(AgentEvent(channel="inproc-test", ...))` is called
- **THEN** the adapter's `received` list has length 1 and contains the event

#### Scenario: End-to-end round-trip through a simple echo subscriber
- **WHEN** the test registers an inbound subscriber that publishes an outbound event back to the same channel
- **AND** the test calls `simulate_inbound("hello world")`
- **THEN** the adapter's `received` list contains an event whose payload includes the original text

## MODIFIED Requirements

### Requirement: Importable azureclaw package
The repository SHALL contain an installable Python package named `azureclaw` rooted at `src/azureclaw/` that exposes a `__version__` string, `AzureClawConfig`, `setup_observability`, and the gateway primitives `create_app`, `GatewayHub`, `ChannelMessage`, `AgentEvent`, `ApprovalRequest`, and `ChannelAdapter`. All symbols SHALL be importable from a fresh `uv sync` of `pyproject.toml`.

#### Scenario: Package imports cleanly after uv sync
- **WHEN** a contributor runs `uv sync` followed by `uv run python -c "import azureclaw; print(azureclaw.__version__)"`
- **THEN** the command exits 0 and prints a non-empty version string

#### Scenario: Editable install registers the package
- **WHEN** a contributor runs `uv pip install -e .`
- **THEN** `python -c "import azureclaw"` succeeds in any working directory

#### Scenario: setup_observability is re-exported from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import setup_observability; print(setup_observability.__name__)"`
- **THEN** the command exits 0 and prints `setup_observability`

#### Scenario: Gateway primitives are re-exported from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import create_app, GatewayHub, ChannelMessage, AgentEvent, ApprovalRequest, ChannelAdapter"`
- **THEN** the import succeeds without raising

### Requirement: Single observability entry point
The package SHALL expose `azureclaw.setup_observability(config: AzureClawConfig) -> None` as the single function every AzureClaw process calls at startup to wire the OpenTelemetry pipeline. The function SHALL be re-exported from `azureclaw.__init__` so callers can `from azureclaw import setup_observability`. The FastAPI gateway's lifespan SHALL call `setup_observability` exactly once at startup so the console or Application Insights exporter is active before any request is served.

#### Scenario: Function is importable from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import setup_observability"`
- **THEN** the import succeeds without raising

#### Scenario: Function accepts a validated AzureClawConfig
- **WHEN** the function is called with an instance of `AzureClawConfig`
- **THEN** it returns `None` (no exceptions raised on any of the three branches: disabled, local, Azure Monitor)

#### Scenario: The gateway lifespan calls setup_observability at startup
- **WHEN** the gateway's FastAPI app is entered via `TestClient(create_app(config))`
- **THEN** `setup_observability` is called exactly once with the same config passed to `create_app`
