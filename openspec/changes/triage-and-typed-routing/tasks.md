## 1. Intent model

- [ ] 1.1 Create `src/azureclaw/orchestrator/__init__.py`
- [ ] 1.2 Create `src/azureclaw/orchestrator/intents.py` with `IntentChat`, `IntentSchedule`, `IntentResearch`, `IntentOnPrem`, `Intent` discriminated union, and `TriageDecision` root model

## 2. Service protocols

- [ ] 2.1 Create `src/azureclaw/orchestrator/services.py` with `TriageService` Protocol (`async classify(text) -> TriageDecision`) and `ChatService` Protocol (`async respond(text, session_id) -> str`), both `@runtime_checkable`

## 3. MAF agent wrappers (production code, not tested in CI)

- [ ] 3.1 Create `src/azureclaw/orchestrator/triage.py` with `MAFTriageService` that wraps `chat_client.as_agent(name="Triage", instructions=TRIAGE_PROMPT, default_options={"response_format": TriageDecision})` and returns `response.value` from `agent.run(text)`
- [ ] 3.2 Create `src/azureclaw/orchestrator/chat.py` with `MAFChatService` that wraps `chat_client.as_agent(name="Chat", instructions=CHAT_PROMPT)` and returns `response.text` from `agent.run(text)`
- [ ] 3.3 Define `TRIAGE_PROMPT` in `triage.py` — enumerates the four intent types with examples so the LLM knows how to produce `TriageDecision` JSON
- [ ] 3.4 Define `CHAT_PROMPT` in `chat.py` — a friendly conversational assistant system prompt

## 4. Orchestrator

- [ ] 4.1 Create `src/azureclaw/orchestrator/orchestrator.py`
- [ ] 4.2 Constructor takes `triage: TriageService`, `chat: ChatService`, `hub: GatewayHub`
- [ ] 4.3 `async start()` subscribes to `hub.subscribe_inbound(self._handle_inbound)`
- [ ] 4.4 `_handle_inbound(msg: ChannelMessage)`:
  - [ ] 4.4.1 Call `triage.classify(msg.text)` to get the `TriageDecision`
  - [ ] 4.4.2 For each intent in `decision.intents`, dispatch to `_handle_intent`
  - [ ] 4.4.3 Fan out multiple intents via `asyncio.gather` with `return_exceptions=True`
  - [ ] 4.4.4 Log exceptions from individual handlers but don't crash the fan-out
- [ ] 4.5 `_handle_intent(intent: Intent, msg: ChannelMessage)`:
  - [ ] 4.5.1 `isinstance(intent, IntentChat)` → call `chat.respond(intent.text, msg.session_id)`, publish `AgentEvent(event_type="completed", payload={"text": reply})`
  - [ ] 4.5.2 `isinstance(intent, IntentSchedule)` → publish stub event with `change_ref="approval-loop-servicebus"`
  - [ ] 4.5.3 `isinstance(intent, IntentResearch)` → publish stub event with `change_ref="magentic-research-team"`
  - [ ] 4.5.4 `isinstance(intent, IntentOnPrem)` → publish stub event with `change_ref="onprem-peer-a2a"`

## 5. Stub service implementations (for tests)

- [ ] 5.1 Create `src/azureclaw/orchestrator/stubs.py` with `StubTriageService(decision: TriageDecision)` and `StubChatService(reply: str)`
- [ ] 5.2 Both are concrete classes satisfying the respective Protocols

## 6. Package re-exports

- [ ] 6.1 Update `src/azureclaw/orchestrator/__init__.py` to re-export `Orchestrator`, `TriageDecision`, `Intent`, `IntentChat`, `IntentSchedule`, `IntentResearch`, `IntentOnPrem`, `TriageService`, `ChatService`, `StubTriageService`, `StubChatService`
- [ ] 6.2 Update `src/azureclaw/__init__.py` to re-export `Orchestrator`, `TriageDecision`

## 7. Tests — intent model

- [ ] 7.1 Create `tests/test_intents.py`
- [ ] 7.2 Test: TriageDecision with IntentChat round-trips through JSON
- [ ] 7.3 Test: TriageDecision with multiple intents preserves all variants
- [ ] 7.4 Test: Unknown kind raises ValidationError
- [ ] 7.5 Test: Each of the four intent types is valid individually

## 8. Tests — orchestrator + round-trip

- [ ] 8.1 Create `tests/test_orchestrator.py`
- [ ] 8.2 Test: chat intent produces a completed event with the chat reply
- [ ] 8.3 Test: schedule intent produces a stub event with change_ref
- [ ] 8.4 Test: research intent produces a stub event with change_ref
- [ ] 8.5 Test: onprem intent produces a stub event with change_ref
- [ ] 8.6 Test: multi-intent message produces multiple events
- [ ] 8.7 Test: full round-trip from InProcTestAdapter through triage → chat → adapter.received
- [ ] 8.8 Test: StubTriageService and StubChatService satisfy their Protocols
- [ ] 8.9 Test: exception from one intent handler does not block others

## 9. Verification

- [ ] 9.1 `uv run ruff check src tests` — clean
- [ ] 9.2 `uv run ruff format --check src tests` — clean
- [ ] 9.3 `uv run pyright src tests` — 0 errors
- [ ] 9.4 `uv run pytest -m local -v` — all existing 82 tests + 10+ new pass
- [ ] 9.5 `npx -y @fission-ai/openspec validate triage-and-typed-routing` — clean

## 10. Commit and PR

- [ ] 10.1 Commit (1) — OpenSpec artifacts — `spec: triage-and-typed-routing — intent model + orchestrator dispatch`
- [ ] 10.2 Commit (2) — implementation — `feat: triage-and-typed-routing implementation`
- [ ] 10.3 Push `feature/triage-and-typed-routing`
- [ ] 10.4 Open PR against `develop`
- [ ] 10.5 Watch CI; merge when green
