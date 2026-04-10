## Context

The bootstrap commit on `main` (`8db506b`) declared `dependencies = []` in `pyproject.toml` and shipped only `.gitkeep` placeholders under `src/azureclaw/`, `tests/`, etc. That was deliberate — the bootstrap was about repo structure, not code. This change is the smallest possible amount of Python that turns the empty package into a valid one and proves the test harness end-to-end.

The hard discipline here is that **no Microsoft Agent Framework dependency lands in this change**, even though MAF is the centerpiece of every later one. MAF carries a substantial dependency tree (azure-ai-foundry SDK, opentelemetry, gRPC clients) and pulling it in before any code uses it would bloat the install for no benefit. MAF lands in the change that introduces the first `ChatAgent`.

Same logic for `azure-keyvault-secrets`, `azure-cosmos`, `azure-search-documents`, `azure-monitor-opentelemetry`, `azure-servicebus`, `azure-storage-blob`, `pywa`, `python-telegram-bot`, `discord.py`, `botbuilder-core`, `playwright`, `mcp`: each one lands with the change that uses it.

## Goals / Non-Goals

**Goals:**

- Make `import azureclaw` work after `uv sync`.
- Make `AzureClawConfig.from_yaml(Path("config.example.yaml"))` parse the example config without raising.
- Make `build_credential("local")` work without `azure.identity` being installed at all (so the local test path is hermetic).
- Ship the first passing `pytest -m local`. CI's `ci/test` gate finally has something to run against.
- Keep the public surface tiny: `azureclaw.AzureClawConfig` and `azureclaw.azure.credential.build_credential`. Nothing else is exported from the package.

**Non-Goals:**

- Defining any agent, workflow, tool, middleware, channel adapter, or memory backend.
- Wiring real Key Vault secret resolution. The `@kv:` syntax is preserved as a literal string for now; the resolver lands with `llm-failover-middleware` (change #6 in the OpenSpec sequence).
- Calling any Azure API. Even the `dev`/`prod` code path of `build_credential` is unreachable in this change because no caller exists yet.
- Refactoring `pyproject.toml` to add ruff configuration changes, type-checker tweaks, or lint rule updates. Those land in their own focused changes when needed.
- Adding `tests/conftest.py` fixtures that are speculative (e.g., a mock Cosmos client). Fixtures land alongside the tests that need them.

## Decisions

### Decision: Pydantic v2 + `pydantic-settings` over `dataclasses` or hand-rolled YAML

**Why:** The config model has ~10 nested sections that will keep growing. Pydantic v2 gives validation, type coercion, JSON-schema export (useful for `config.example.yaml` documentation), and good error messages with field paths. `pydantic-settings` lets later changes layer environment-variable overrides on top of the YAML without rewriting the model. `dataclasses` is fine for small objects but lacks the validation surface; a hand-rolled approach would mean writing the same boilerplate per section.

**Alternatives considered:** `attrs + cattrs` (good but smaller ecosystem inside Microsoft tooling); `dataclasses + dacite` (rejected: less validation); raw `dict` (rejected: no type checker friendliness, defeats pyright strict mode).

### Decision: `azureclaw.azure.credential` is import-safe without `azure.identity`

**Why:** The local test marker exists so contributors and CI can validate the orchestrator/middleware/memory paths without an Azure subscription. If importing `azureclaw.azure.credential` always pulled in `azure.identity`, the local marker would still need that package installed, which is a friction tax for no benefit. The fix is to import `azure.identity` *inside* the `dev`/`prod` branch of `build_credential`, behind a runtime check. The local stub is a tiny standalone class.

**Alternatives considered:** Always import `azure.identity` at module top (rejected: forces it onto the local-fallback path); split the file into two modules `credential_local.py` and `credential_azure.py` (rejected: callers would have to know which one to use, defeating the "single entry point" design).

### Decision: The credential stub is a private class, not an exported helper

**Why:** Returning a `_LocalStubCredential` from the public function keeps the contract simple ("you get something with `get_token()`") and prevents callers from constructing the stub directly in production code. The leading underscore is the documentation.

**Alternatives considered:** Export it as `LocalStubCredential` (rejected: invites misuse); use `unittest.mock.Mock` (rejected: lifecycle weirdness, harder to type-annotate).

### Decision: `from_yaml` is a classmethod on the model, not a top-level function

**Why:** Discoverability. `AzureClawConfig.from_yaml(path)` reads naturally and shows up under the model in any IDE's autocomplete. A top-level `load_config(path)` function would be one more name to remember.

**Alternatives considered:** Top-level `load_config()` (rejected for the reason above); accept either a path or a string (rejected: ambiguous; the test can `Path(...)` itself).

### Decision: Tests live under `tests/` and use `pytest`'s built-in marker mechanism

**Why:** Already declared in the bootstrap's `pyproject.toml`. Just need to ship the first test files.

### Decision: Replace empty `__init__.py` placeholders only where this change actually creates Python

**Why:** `src/azureclaw/.gitkeep` becomes `src/azureclaw/__init__.py` because we're creating that package. `azureclaw-bridge/`, `infra/`, and `docs/` keep their `.gitkeep`s — they're not Python packages and shouldn't get an `__init__.py`. `tests/` gets an `__init__.py` because it makes pytest's test discovery more predictable on Windows.

**Alternatives considered:** Convert all `.gitkeep`s to `__init__.py` (rejected: wrong for non-Python directories); leave `.gitkeep` next to `__init__.py` (rejected: redundant).

## Risks / Trade-offs

- **Risk:** Pydantic v2 has had breaking API changes between minors. → **Mitigation:** pin a `>=2.5,<3` constraint in `pyproject.toml`; the model uses only the stable surface (`BaseModel`, `Field`, `model_validate`).

- **Risk:** The `local` stub credential is a duck-typed object, not a real `TokenCredential`. If a future change imports `azure.core.credentials.TokenCredential` and runtime-checks against it, the stub will fail isinstance. → **Mitigation:** the contract is documented as "structural" — `get_token()` is what matters. If a future caller needs a real `TokenCredential`, that change can either widen the stub or branch on environment.

- **Risk:** `pyright` strict mode may flag the `_LocalStubCredential` as not satisfying `TokenCredential`'s protocol. → **Mitigation:** declare `_LocalStubCredential` as implementing the same protocol shape (one method, `get_token`), and have `build_credential`'s return type be a `Protocol` we control rather than `azure.core.credentials.TokenCredential`. The `dev`/`prod` path's `DefaultAzureCredential` instance satisfies our protocol structurally.

- **Risk:** `config.example.yaml` may grow new sections in later changes, and this model becomes the gating contract for those changes. → **Mitigation:** the model uses `dict | None = None` for fields whose internal structure is still being designed (`memory.cosmos`, `tools.browser`, etc.). Only the section names are locked in this change. Each later change tightens its own section's typing.

- **Risk:** Adding 4 new runtime dependencies (`pydantic`, `pydantic-settings`, `pyyaml`, `azure-identity`) measurably grows the install. → **Mitigation:** these are foundational to every later change anyway; pulling them in now is honest. The total install is still tiny — no MAF, no Azure SDK clients, no channel SDKs.

## Migration Plan

This is greenfield code added on top of an empty package. There is no migration. The only "after" state is:

1. `src/azureclaw/__init__.py`, `src/azureclaw/config.py`, `src/azureclaw/azure/__init__.py`, `src/azureclaw/azure/credential.py` exist.
2. `tests/__init__.py`, `tests/conftest.py`, `tests/test_config_loads.py`, `tests/test_credential_local_stub.py` exist.
3. `pyproject.toml` declares 4 new runtime dependencies.
4. The `src/azureclaw/.gitkeep` and `tests/.gitkeep` files are deleted (replaced by their respective `__init__.py`).
5. `uv run pytest -m local` exits 0.
6. `ci/test` finally has something to assert against.

**Rollback:** revert the PR. Nothing outside the repository is affected.

## Open Questions

- Should `build_credential` accept the full `AzureClawConfig` instead of just the environment string? (Deferred: the current signature is the smallest one that works; later changes can widen it without a breaking change because positional parameter additions on a single-caller function are cheap to refactor.)
- Should `tests/conftest.py` register a `pytest_collection_modifyitems` hook that auto-marks every test under `tests/` as `local` unless it carries another marker? (Deferred: explicit markers are clearer for the first few tests; revisit when the suite has 20+ tests.)
