## Why

The orchestrator classifies inbound messages and dispatches by intent type. `IntentResearch` (browse a URL, summarize content, look up information) currently emits a stub event. This change replaces that stub with a real multi-agent research team built on MAF's **MagenticBuilder** — the Magentic-One orchestration pattern from Microsoft Research, where a **manager agent** dynamically picks which worker agent speaks next, detects stalls, and emits a final answer.

This is the first use of **multi-agent orchestration** in AzureClaw. Every prior change used single-agent calls. The Magentic-One pattern demonstrates that AzureClaw can compose multiple agents collaboratively via MAF's built-in orchestration infrastructure rather than hand-rolling a group-chat loop.

## What Changes

- Add `agent-framework-orchestrations>=1.0.0b260409,<2` to `pyproject.toml` (just 1 new package; contains `MagenticBuilder`, `WorkflowAgent`, `GroupChatBuilder`, `HandoffBuilder`, `SequentialBuilder`, `ConcurrentBuilder`)
- Add `ResearchService` Protocol to `src/azureclaw/orchestrator/services.py`: `async research(query: str, url: str | None) -> str`
- Add `StubResearchService` to `src/azureclaw/orchestrator/stubs.py`
- Create `src/azureclaw/orchestrator/research_team.py` with `MAFResearchService` — the production implementation:
  - Constructs a `MagenticBuilder` workflow with three participant agents: Browser (stub instructions for now — Playwright MCP tool lands later), Summarizer, and an optional Canvas agent
  - Uses a manager agent that decides which worker to activate next and when the task is done
  - Wraps the built workflow in `WorkflowAgent` and calls `.run(task_text)` at research time
  - Returns the final answer text
- Update `src/azureclaw/orchestrator/orchestrator.py`:
  - Constructor accepts optional `research: ResearchService | None = None`
  - `_handle_intent` for `IntentResearch`: if `self._research` is set, delegates to it and publishes the result as a completed event; otherwise falls through to the existing stub event (backward compatible)
- Update re-exports in `__init__.py` files
- Add tests proving the research intent now produces a real response via `StubResearchService`

**Non-goals:**
- Real Playwright MCP browser tool (lands in a later change)
- Real URL fetching or web scraping
- Cosmos-backed checkpointing for the research workflow (lands with `memory-cosmos-aisearch`)
- Canvas/Blob Storage persistence of research results
- Any real LLM call in CI tests

## Capabilities

### New Capabilities

- `research-team`: the `ResearchService` Protocol, its `MAFResearchService` production implementation using `MagenticBuilder` + `WorkflowAgent`, and the stub for tests

### Modified Capabilities

- `intent-routing`: `IntentResearch` now dispatches to `ResearchService.research()` when a research service is provided; falls through to the stub event when not

## Impact

- **Affected systems:** local working tree only
- **Affected dependencies:** `pyproject.toml` gains `agent-framework-orchestrations>=1.0.0b260409,<2` (1 package)
- **Affected APIs:** `Orchestrator` constructor gains an optional `research` parameter
- **Reversibility:** fully reversible — revert the PR
