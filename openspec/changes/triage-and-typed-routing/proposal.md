## Why

AzureClaw has a gateway, a hub, an LLM provider stack with failover, and observability. What it does NOT have is any code that **does something** with an inbound message. An inbound `ChannelMessage` arrives at the hub and has no subscriber. This change wires the first subscriber: a Triage classifier that reads the user's intent, a discriminated-union intent model that describes what the user wants, and an Orchestrator that dispatches by intent type to specialized handlers. The first real handler is the Chat agent (pure conversation); the other three intent types (Schedule, Research, OnPrem) route to stubs that return "not yet implemented" events, setting up the extension points that later changes deliver on.

This is the change that turns AzureClaw from a collection of plumbing into a real **agent system**.

## What Changes

- Create `src/azureclaw/orchestrator/__init__.py` re-exporting the public surface
- Create `src/azureclaw/orchestrator/intents.py` with a Pydantic v2 discriminated union:
  - `IntentChat` — pure conversation
  - `IntentSchedule` — reminders / cron (stub handler; real handler lands in `approval-loop-servicebus`, change #10)
  - `IntentResearch` — web browse / summarize (stub; real handler lands in `magentic-research-team`, change #8)
  - `IntentOnPrem` — commands at a user's site (stub; real handler lands in `onprem-peer-a2a`, change #18)
  - `Intent` — the `Annotated` discriminated union type
  - `TriageDecision` — root model with `intents: list[Intent]` supporting concurrent multi-intent messages
- Create `src/azureclaw/orchestrator/services.py` with two `@runtime_checkable` Protocols:
  - `TriageService` — `async classify(text) -> TriageDecision`
  - `ChatService` — `async respond(text, session_id) -> str`
- Create `src/azureclaw/orchestrator/triage.py` with `MAFTriageService` — wraps `chat_client.as_agent(name="Triage", default_options={"response_format": TriageDecision})` and calls `agent.run(text)`, extracts `response.value`
- Create `src/azureclaw/orchestrator/chat.py` with `MAFChatService` — wraps `chat_client.as_agent(name="Chat")` and returns `response.text`
- Create `src/azureclaw/orchestrator/orchestrator.py` with the `Orchestrator` class:
  - Constructor: `(triage, chat, hub)` — protocol-injected services + the gateway hub
  - `async start()` — subscribes to `hub.subscribe_inbound`
  - `_handle_inbound(msg)` — calls triage.classify, iterates intents, dispatches by type, publishes outbound events. Multiple intents fan out via `asyncio.gather`. Stub intents emit events with `payload={"stub": True, "change_ref": "..."}`.
- Create `tests/test_intents.py` — intent model validation, discriminated union dispatch, JSON round-trip
- Create `tests/test_orchestrator.py` — end-to-end round-trip using `StubTriageService` + `StubChatService` + `InProcTestAdapter` against the hub; proves the inbound → triage → chat → outbound pipeline works
- Re-export `Orchestrator`, `TriageDecision`, `Intent`, and the four intent types from `azureclaw.__init__`

**Non-goals (explicitly not in this change):**
- MAF WorkflowBuilder. The orchestrator uses plain Python dispatch-by-isinstance in this change. WorkflowBuilder lands with `magentic-research-team` (#8) which has a multi-step graph that justifies the abstraction.
- Real LLM calls. The MAF agent wrappers (`MAFTriageService`, `MAFChatService`) are production code but are NOT exercised in CI; tests use stub services that return canned decisions.
- Gateway lifespan wiring of the orchestrator. The orchestrator is a standalone module; the lifespan integration (build_chat_client → build services → start orchestrator) requires provider credentials and is deferred to a follow-up integration change.
- Any channel adapter. The `InProcTestAdapter` is the only test surface.
- Session memory. The triage agent is stateless in this change; context providers land with `memory-cosmos-aisearch` (#9).

## Capabilities

### New Capabilities

- `intent-routing`: the `TriageDecision` discriminated union, the `TriageService` / `ChatService` protocols, and the `Orchestrator` dispatch loop
- `triage-agent`: the `MAFTriageService` wrapper that calls a `ChatAgent` with `response_format=TriageDecision` via the Responses API structured-output mechanism

### Modified Capabilities

- `package-skeleton`: the `azureclaw` package gains new re-exports (`Orchestrator`, `TriageDecision`, `Intent`, `IntentChat`, `IntentSchedule`, `IntentResearch`, `IntentOnPrem`)

## Impact

- **Affected systems:** local working tree only; no Azure resource is touched
- **Affected dependencies:** no new `pyproject.toml` deps (this change only uses `agent-framework-core` which was already pulled in by `observability-appinsights`)
- **Affected APIs:** introduces the orchestrator subpackage + the intent model + the services + the Orchestrator class
- **Reversibility:** fully reversible — revert the PR. No external state.
