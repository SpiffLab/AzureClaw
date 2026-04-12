## ADDED Requirements

### Requirement: TriageDecision is a Pydantic v2 discriminated union
The package SHALL expose `azureclaw.orchestrator.intents.TriageDecision` as a Pydantic v2 model with a single field `intents: list[Intent]`. `Intent` is a discriminated union (`Annotated[..., Discriminator("kind")]`) of `IntentChat`, `IntentSchedule`, `IntentResearch`, and `IntentOnPrem`. Every variant carries a `kind: Literal["..."]` field that discriminates the union.

#### Scenario: TriageDecision round-trips through JSON
- **WHEN** a `TriageDecision` instance with two intents (one `IntentChat`, one `IntentSchedule`) is serialized via `model_dump(mode="json")` and reconstructed via `model_validate`
- **THEN** the reconstructed instance equals the original
- **AND** the first intent is an `IntentChat` and the second is an `IntentSchedule`

#### Scenario: TriageDecision rejects an unknown intent kind
- **WHEN** a JSON payload with `{"intents": [{"kind": "nope"}]}` is passed to `TriageDecision.model_validate`
- **THEN** a `pydantic.ValidationError` is raised

#### Scenario: TriageDecision supports concurrent multi-intent messages
- **WHEN** a TriageDecision has `intents` of length 2 (e.g., `[IntentSchedule(...), IntentResearch(...)]`)
- **THEN** the model is valid and both intents are preserved

### Requirement: Orchestrator dispatches inbound messages by intent type
The package SHALL expose `azureclaw.orchestrator.orchestrator.Orchestrator` that takes a `TriageService`, a `ChatService`, and a `GatewayHub` at construction. After `start()`, it subscribes to `hub.subscribe_inbound`. On each `ChannelMessage` it calls `triage.classify(msg.text)`, iterates the returned intents, and dispatches each by type: `IntentChat` delegates to `chat.respond()` and publishes an outbound `AgentEvent` with the response text; all other intent types publish a stub `AgentEvent` with `payload.stub = True` and a `change_ref` string naming the OpenSpec change that will deliver the real handler.

#### Scenario: Chat intent produces a real response
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentChat(text="hello")])`
- **AND** `ChatService.respond` returns `"Hi there!"`
- **THEN** the orchestrator publishes one `AgentEvent` whose `event_type == "completed"` and `payload["text"] == "Hi there!"`

#### Scenario: Schedule intent produces a stub event
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentSchedule(description="remind me", when="5pm")])`
- **THEN** the orchestrator publishes one `AgentEvent` whose `payload["stub"] == True`
- **AND** `payload["change_ref"]` contains `"approval-loop-servicebus"`

#### Scenario: Research intent produces a stub event
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentResearch(query="summarize this")])`
- **THEN** the orchestrator publishes one `AgentEvent` whose `payload["stub"] == True`
- **AND** `payload["change_ref"]` contains `"magentic-research-team"`

#### Scenario: OnPrem intent produces a stub event
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentOnPrem(site_id="home", action="list shares")])`
- **THEN** the orchestrator publishes one `AgentEvent` whose `payload["stub"] == True`
- **AND** `payload["change_ref"]` contains `"onprem-peer-a2a"`

#### Scenario: Multiple intents fan out concurrently
- **WHEN** `TriageService.classify` returns a `TriageDecision` with two intents
- **THEN** both intents produce outbound events
- **AND** both events land in the adapter's `received` list

### Requirement: End-to-end round-trip from InProcTestAdapter through the orchestrator
The orchestrator SHALL support a full round-trip from `InProcTestAdapter.simulate_inbound` through the triage and chat services back to the adapter's `received` list.

#### Scenario: Full round-trip works
- **WHEN** `InProcTestAdapter.simulate_inbound("hello world")` is called
- **AND** the stub triage returns `TriageDecision(intents=[IntentChat(text="hello world")])`
- **AND** the stub chat returns `"echo: hello world"`
- **THEN** `adapter.received` has length 1
- **AND** `adapter.received[0].event_type == "completed"`
- **AND** `adapter.received[0].payload["text"] == "echo: hello world"`

### Requirement: TriageService and ChatService are protocols
The orchestrator SHALL accept `TriageService` and `ChatService` as `@runtime_checkable` Protocols, not concrete classes. This enables dependency injection: tests inject stubs; production injects MAF agent wrappers.

#### Scenario: Stub services satisfy the protocols
- **WHEN** a `StubTriageService` (that returns a canned `TriageDecision`) is checked via `isinstance(stub, TriageService)`
- **THEN** the check returns True

#### Scenario: MAF agent wrappers satisfy the protocols
- **WHEN** `MAFTriageService` is checked via `isinstance(instance, TriageService)`
- **THEN** the check returns True
