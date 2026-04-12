## Context

Six OpenSpec changes have landed: config model, credential factory, Bicep blueprint, MAF observability, FastAPI gateway with hub, and the LLM provider stack with failover. The gateway has a hub that fans out inbound messages — but with zero subscribers. This change wires the first subscriber: a Triage classifier that reads the user's intent, a typed intent model that makes routing testable, and an Orchestrator that dispatches by intent type to specialized handlers.

Design-critical decision: **protocol-based services, not direct MAF coupling**. The orchestrator talks to `TriageService` and `ChatService` via thin Protocols. In production, those protocols are satisfied by `MAFTriageService` and `MAFChatService` wrappers that use `chat_client.as_agent(...)` under the hood. In tests, they're satisfied by `StubTriageService(canned_decision)` and `StubChatService(canned_reply)` which return instantly with no MAF, no chat client, no mock setup, no `ChatResponse` construction. This keeps the orchestrator's logic testable in isolation.

## Goals / Non-Goals

**Goals:**

- Ship the `TriageDecision` discriminated union as the single routing contract every later change respects.
- Ship the `Orchestrator` class that subscribes to the hub and dispatches by intent type. The first real handler is Chat; the other three are stubs that emit `{"stub": true, "change_ref": "..."}` events so later changes know exactly what to replace.
- Prove the full inbound → triage → dispatch → outbound pipeline works via a test using `InProcTestAdapter` + stub services.
- Make the MAF agent wrappers available as production code (`MAFTriageService`, `MAFChatService`) but NOT exercise them in CI (no credentials).

**Non-Goals:**

- MAF `WorkflowBuilder`. Plain Python dispatch-by-isinstance is sufficient for a single-step graph with four branches. `WorkflowBuilder` lands with `magentic-research-team` (#8) where the multi-step research flow justifies a real graph.
- Gateway lifespan wiring. The orchestrator requires a chat client, which requires provider credentials. The lifespan integration is deferred; tests construct the orchestrator manually.
- Real LLM calls.
- Session memory or context providers.
- Tool execution or function invocation.

## Decisions

### Decision: Protocol-based services instead of direct `Agent` injection

**Why:** Injecting `Agent` objects into the orchestrator couples the orchestrator's test suite to MAF's `AgentResponse` shape, which requires constructing `ChatResponse` objects whose internal API is non-trivial (message lists, response_format, continuation tokens). A thin Protocol (`async classify(text) -> TriageDecision` for triage, `async respond(text, session_id) -> str` for chat) decouples completely: the test stubs are three-line classes, and the orchestrator tests focus on routing logic, not on mocking MAF internals.

The cost is an extra layer of indirection at the boundary. The benefit is that every orchestrator test is hermetic, fast, and doesn't import any provider SDK.

### Decision: Discriminated union via `Annotated[..., Discriminator("kind")]`

**Why:** Pydantic v2's native discriminated union is the cleanest way to express "this field is one of N variants, distinguished by the `kind` field." It:
- Gives us JSON Schema generation for free (which the Responses API/structured output mechanism needs)
- Validates at parse time (a `kind` value outside the allowed set raises `ValidationError`)
- Discriminates at match time (`isinstance(intent, IntentChat)`) for readable dispatch

### Decision: `intents` is a `list[Intent]`, not a single `Intent`

**Why:** Real user messages are often compound: "remind me to defrost the lobster at 6pm AND summarize this recipe URL." The plan explicitly calls out concurrent fan-out for multi-intent messages. Having `intents` be a list from day one means the triage prompt and the orchestrator dispatch loop are designed for the multi-intent case from the start, even though the MVP tests exercise single-intent messages.

### Decision: Stub handlers emit `{"stub": True, "change_ref": "..."}` events

**Why:** Each later change (#8 magentic-research-team, #10 approval-loop-servicebus, #18 onprem-peer-a2a) needs to find and replace its stub handler. A structured `stub` payload with a `change_ref` string makes that search-and-replace explicit: `grep -r 'change_ref.*magentic-research-team'` finds the exact line to replace. Without the `change_ref`, a developer would have to read every `if isinstance(intent, IntentResearch)` block to figure out which is the stub and which is the real implementation.

### Decision: `asyncio.gather` for multi-intent fan-out

**Why:** The simplest way to run N async tasks concurrently. Each intent handler is a coroutine; `gather` runs them in parallel and collects exceptions. A `WorkflowBuilder` graph would be more powerful (checkpointing, human-in-the-loop pauses between steps) but overkill for "run three coroutines and wait for all." `WorkflowBuilder` lands when the research flow needs it.

## Risks / Trade-offs

- **Risk:** The protocol-based service pattern adds a layer that someone might skip, injecting a real MAF agent into the orchestrator directly. → **Mitigation:** the constructor type hints enforce the Protocol at static-analysis time. Pyright will flag an `Agent` passed where `TriageService` is expected.

- **Risk:** The stub handlers emit events that look like real responses (they have `event_type="completed"`). A downstream component might act on them. → **Mitigation:** the `payload["stub"] = True` flag is the universal "this is a placeholder" marker. Any downstream component that processes stub events should check that flag.

- **Risk:** The `MAFTriageService` and `MAFChatService` are untested in CI because they require a real chat client. → **Mitigation:** acceptable for the MVP. The nightly Azure-marker tests (once they exist) will exercise them.

## Migration Plan

Post-merge state:

1. `src/azureclaw/orchestrator/` exists with `intents.py`, `services.py`, `triage.py`, `chat.py`, `orchestrator.py`.
2. `TriageDecision`, `Intent`, `IntentChat/Schedule/Research/OnPrem`, and `Orchestrator` are re-exported from the package root.
3. The orchestrator module is standalone — no gateway lifespan wiring.
4. `pytest -m local` passes with the existing 82 tests + 10+ new orchestrator tests.

**Rollback:** revert the PR. No external state.

## Open Questions

- Should the orchestrator catch exceptions from individual intent handlers and continue with the remaining intents? **Yes** — consistent with the hub's "raising subscriber doesn't break fan-out" contract. Implement in this change.
- Should `MAFTriageService` pass a system prompt alongside the user text? **Yes** — the triage prompt enumerates the four intent types and their schemas. The prompt is a constant string in `triage.py`.
