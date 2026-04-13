## Context

Seven changes in. The orchestrator classifies messages via Triage and dispatches by intent type. `IntentChat` has a real handler; `IntentResearch` emits a stub event. This change replaces the research stub with a real multi-agent team built on MAF's Magentic-One pattern.

The Magentic-One pattern (from Microsoft Research / AutoGen) is a "manager + workers" design: a **manager agent** dynamically picks which worker speaks next based on the current state of the task, detects when a worker stalls, and emits a final answer. It's a genuinely multi-agent flow — different from the single-agent Triage→Chat path.

API discovery confirmed: `agent-framework-orchestrations` (a separate package from `agent-framework-core`) provides `MagenticBuilder`, `MagenticOrchestrator`, `WorkflowAgent`. The builder takes participant agents + a manager agent, builds a `Workflow`, and `WorkflowAgent(workflow).run(task)` drives the multi-round conversation.

## Goals / Non-Goals

**Goals:**

- Ship the `ResearchService` Protocol and its stub, following the same pattern as `TriageService` / `ChatService`.
- Ship `MAFResearchService` that creates a Magentic-One team workflow with Browser + Summarizer workers and a manager agent. The browser agent is a stub (no real tool); it has instructions saying what it WOULD do. The Playwright MCP tool lands later.
- Wire the orchestrator's `IntentResearch` handler to use the research service instead of emitting a stub event.
- Backward compatible: the orchestrator defaults `research=None` and falls through to the stub event when no service is provided.
- Demonstrate the MagenticBuilder API end-to-end so later changes (Canvas agent, on-prem A2A peer worker) can follow the same pattern.

**Non-Goals:**

- Real Playwright MCP browser tool (separate change)
- Real URL fetching
- Checkpointing for the research workflow
- Real LLM calls in tests
- Changing any existing test (backward compat via optional parameter)

## Decisions

### Decision: `agent-framework-orchestrations` as a separate dep (1 package, not the umbrella)

**Why:** The orchestration patterns are in a dedicated package that depends only on `agent-framework-core`. It adds zero extra transitive deps. Installing the full `agent-framework` umbrella would have added 90+ packages we don't need.

### Decision: Follow the services Protocol pattern from change #7

**Why:** `ResearchService` is a Protocol with one method (`research(query, url) -> str`). Tests use `StubResearchService("canned answer")`. `MAFResearchService(chat_client)` is the production implementation. This is exactly the same pattern as `TriageService` / `ChatService` — adding it is a 3-minute review for anyone who's seen the previous change.

### Decision: The browser agent inside MAFResearchService is a stub (instructions only, no MCP tool)

**Why:** The Playwright MCP server hasn't been built yet. The agent has a system prompt saying "you are a browser agent capable of fetching web pages" and responds as if it browsed. In the Magentic-One flow, the manager will ask the browser agent for content, the browser agent will synthesize an answer from the LLM's training data, and the summarizer will condense it. Not useful for real browsing, but sufficient to prove the multi-agent wiring works. When the real Playwright MCP tool lands, the browser agent gains the `tools=[mcp_browser]` parameter.

### Decision: Orchestrator accepts `research` as optional parameter, not required

**Why:** Backward compatibility. All existing tests construct `Orchestrator(triage, chat, hub)` without a research service. Making it required would break them all. The `None` default means "emit the stub event like before." Tests that exercise the research path explicitly pass a `StubResearchService`.

## Risks / Trade-offs

- **Risk:** `agent-framework-orchestrations` is a beta release. → **Mitigation:** same pattern as `agent-framework-anthropic`; pinned floor, accept beta churn.
- **Risk:** The browser stub agent talks nonsense since it has no real browsing capability. → **Mitigation:** acceptable; the stub is clearly documented and the Playwright MCP tool change will replace it.
- **Risk:** The Magentic-One flow may produce verbose output (multiple rounds of manager↔worker conversation). → **Mitigation:** the research service extracts only `response.text` (the final answer) and discards the intermediate conversation.

## Migration Plan

Post-merge state:
1. `ResearchService` Protocol + `StubResearchService` + `MAFResearchService` exist.
2. `Orchestrator` accepts optional `research` parameter.
3. `IntentResearch` dispatches to the research service when provided.
4. `pyproject.toml` declares `agent-framework-orchestrations`.
5. All existing tests pass unchanged. New tests cover the research dispatch.

**Rollback:** revert the PR.

## Open Questions

- Should `MAFResearchService` cache the built workflow so it's reused across calls? **Yes, and it does** — the workflow is built once in `__init__` and reused in every `research()` call. Each call creates a fresh `WorkflowAgent` session so conversation state doesn't leak.
