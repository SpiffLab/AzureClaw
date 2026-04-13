## ADDED Requirements

### Requirement: ResearchService Protocol
The package SHALL expose `azureclaw.orchestrator.services.ResearchService` as a `@runtime_checkable` Protocol with a single method: `async research(self, query: str, url: str | None) -> str`. The method SHALL return a text summary of the research result.

#### Scenario: Protocol is reachable
- **WHEN** `from azureclaw.orchestrator.services import ResearchService` is called
- **THEN** the import succeeds without raising

#### Scenario: StubResearchService satisfies the protocol
- **WHEN** `isinstance(StubResearchService("result"), ResearchService)` is checked
- **THEN** the check returns True

### Requirement: StubResearchService for hermetic tests
The package SHALL expose `azureclaw.orchestrator.stubs.StubResearchService` that takes a canned result string at construction and returns it from every `research()` call.

#### Scenario: Stub returns canned result
- **WHEN** `StubResearchService("summary").research("query", None)` is awaited
- **THEN** the result is `"summary"`

### Requirement: MAFResearchService uses MagenticBuilder for multi-agent orchestration
The package SHALL expose `azureclaw.orchestrator.research_team.MAFResearchService` that:

1. Constructs a `MagenticBuilder` workflow at init time with at least two participant agents (Browser, Summarizer) and a manager agent
2. Wraps the built workflow in a `WorkflowAgent`
3. Calls `workflow_agent.run(task_text)` when `research()` is invoked and returns the response text

This is the first multi-agent orchestration in AzureClaw — the Magentic-One pattern from Microsoft Research, where the manager dynamically picks which worker speaks next.

#### Scenario: MAFResearchService constructs without error
- **WHEN** `MAFResearchService(chat_client)` is constructed with a valid `BaseChatClient`
- **THEN** no exception is raised
- **AND** the service holds a `WorkflowAgent` internally

### Requirement: IntentResearch dispatches to ResearchService when provided
The `Orchestrator` constructor SHALL accept an optional `research: ResearchService | None = None` parameter. When an `IntentResearch` is classified:

- If `self._research` is set: call `research.research(intent.query, intent.url)` and publish the result as an `AgentEvent(event_type="completed", payload={"text": result})`
- If `self._research` is None: fall through to the existing stub event (backward compatible)

#### Scenario: Research intent with service produces a real response
- **WHEN** the orchestrator is constructed with a `StubResearchService("research summary")`
- **AND** triage classifies a message as `IntentResearch(query="summarize this")`
- **THEN** the adapter receives one `AgentEvent` with `payload["text"] == "research summary"`
- **AND** `payload.get("stub")` is not True

#### Scenario: Research intent without service produces a stub event
- **WHEN** the orchestrator is constructed with `research=None`
- **AND** triage classifies a message as `IntentResearch(query="summarize this")`
- **THEN** the adapter receives one `AgentEvent` with `payload["stub"] == True`
- **AND** `payload["change_ref"]` contains `"magentic-research-team"`

#### Scenario: Existing chat/schedule/onprem tests still pass unchanged
- **WHEN** the orchestrator is constructed with `research=None` (the default)
- **THEN** all existing test_orchestrator.py tests pass without modification

## MODIFIED Requirements

### Requirement: Orchestrator dispatches inbound messages by intent type
The package SHALL expose `azureclaw.orchestrator.orchestrator.Orchestrator` that takes a `TriageService`, a `ChatService`, an optional `ResearchService`, and a `GatewayHub` at construction. After `start()`, it subscribes to `hub.subscribe_inbound`. On each `ChannelMessage` it calls `triage.classify(msg.text)`, iterates the returned intents, and dispatches each by type: `IntentChat` delegates to `chat.respond()` and publishes an outbound `AgentEvent` with the response text; `IntentResearch` delegates to `research.research()` when the service is provided; all other intent types publish a stub `AgentEvent` with `payload.stub = True` and a `change_ref` string naming the OpenSpec change that will deliver the real handler.

#### Scenario: Chat intent produces a real response
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentChat(text="hello")])`
- **AND** `ChatService.respond` returns `"Hi there!"`
- **THEN** the orchestrator publishes one `AgentEvent` whose `event_type == "completed"` and `payload["text"] == "Hi there!"`

#### Scenario: Research intent with service produces a real response
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentResearch(query="summarize")])`
- **AND** `ResearchService.research` returns `"Summary here"`
- **THEN** the orchestrator publishes one `AgentEvent` whose `payload["text"] == "Summary here"`

#### Scenario: Schedule intent produces a stub event
- **WHEN** `TriageService.classify` returns `TriageDecision(intents=[IntentSchedule(description="remind me", when="5pm")])`
- **THEN** the orchestrator publishes one `AgentEvent` whose `payload["stub"] == True`

#### Scenario: Multiple intents fan out concurrently
- **WHEN** `TriageService.classify` returns a `TriageDecision` with two intents
- **THEN** both intents produce outbound events
