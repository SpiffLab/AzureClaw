## 1. Dependencies

- [ ] 1.1 Add `agent-framework-orchestrations>=1.0.0b260409,<2` to `pyproject.toml`
- [ ] 1.2 `uv sync --extra dev` and confirm lockfile picks up 1 new package

## 2. ResearchService Protocol + stub

- [ ] 2.1 Add `ResearchService` Protocol to `services.py`: `async research(query, url) -> str`
- [ ] 2.2 Add `StubResearchService(result: str)` to `stubs.py`
- [ ] 2.3 Update `orchestrator/__init__.py` re-exports

## 3. MAFResearchService (production, not CI-tested)

- [ ] 3.1 Create `src/azureclaw/orchestrator/research_team.py`
- [ ] 3.2 Define `BROWSER_PROMPT`, `SUMMARIZER_PROMPT`, `MANAGER_PROMPT` constants
- [ ] 3.3 Construct 3 agents: Browser (stub instructions), Summarizer, Manager
- [ ] 3.4 Build `MagenticBuilder(participants=[browser, summarizer], manager_agent=manager, max_stall_count=3).build()` → Workflow
- [ ] 3.5 `research()` creates `WorkflowAgent(workflow)`, calls `.run(task_text)`, returns `.text`

## 4. Orchestrator update

- [ ] 4.1 Add `research: ResearchService | None = None` to `Orchestrator.__init__`
- [ ] 4.2 In `_handle_intent` for `IntentResearch`: if `self._research` is set, call `research.research(intent.query, intent.url)` and publish result; else fall through to existing stub event

## 5. Tests

- [ ] 5.1 Create `tests/test_research_team.py`
- [ ] 5.2 Test: StubResearchService satisfies ResearchService Protocol
- [ ] 5.3 Test: StubResearchService returns canned result
- [ ] 5.4 Test: research intent with service produces a real (non-stub) response via InProcTestAdapter
- [ ] 5.5 Test: research intent without service still produces a stub event (backward compat)
- [ ] 5.6 Test: existing orchestrator tests still pass (run full suite)

## 6. Verification

- [ ] 6.1 `uv run ruff check / format --check` — clean
- [ ] 6.2 `uv run pyright src tests` — 0 errors
- [ ] 6.3 `uv run pytest -m local` — all existing 99 + new tests pass
- [ ] 6.4 `npx openspec validate magentic-research-team` — clean

## 7. Commit and PR

- [ ] 7.1 Commit (1) — spec — `spec: magentic-research-team — MagenticBuilder multi-agent research team`
- [ ] 7.2 Commit (2) — implementation — `feat: magentic-research-team implementation`
- [ ] 7.3 Push, PR, watch CI, merge
