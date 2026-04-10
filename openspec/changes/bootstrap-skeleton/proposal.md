## Why

The bootstrap commit established the repository's structural conventions but committed zero Python code. Every later OpenSpec change (Triage agent, Magentic team, Cosmos memory, channel adapters, …) needs three things to exist before it can be implemented: an importable `azureclaw` package, a typed configuration model that loads `config.example.yaml`, and a unified Azure credential factory that every Azure-touching module routes through. This change adds those three foundations and proves them with a passing local test suite — nothing more.

The constraint is deliberate: this is the smallest amount of Python that unblocks the next change, not a "let's wire everything up" PR.

## What Changes

- Add real runtime dependencies to `pyproject.toml`: `pydantic`, `pydantic-settings`, `pyyaml`, `azure-identity` (the `dev` extras already declared in the bootstrap stay where they are)
- Create `src/azureclaw/__init__.py` exposing `__version__ = "0.0.0"` and a docstring describing the package
- Create `src/azureclaw/config.py` with a Pydantic v2 model hierarchy mirroring `config.example.yaml`'s sections (environment, providers, embeddings, memory, channels, tools, safety, observability, hybrid, a2a) plus a classmethod `AzureClawConfig.from_yaml(path)` that parses a YAML file into a validated model
- Create `src/azureclaw/azure/__init__.py` (empty subpackage marker)
- Create `src/azureclaw/azure/credential.py` exposing `build_credential(environment)` which returns `DefaultAzureCredential` for `dev`/`prod` and a stub credential for `local` (so local tests run without any az-cli login state and without importing `azure.identity`)
- Create `tests/__init__.py` and `tests/conftest.py` (minimal pytest plugin discovery)
- Create `tests/test_config_loads.py` proving `config.example.yaml` parses into the model with no validation errors
- Create `tests/test_credential_local_stub.py` proving `build_credential("local")` returns a credential whose `get_token()` is callable without making any network call
- Replace each previously empty package directory's `.gitkeep` with the corresponding `__init__.py` only where this change is actually creating Python; `azureclaw-bridge/`, `infra/`, and `docs/` keep their `.gitkeep`s

**Non-goals (explicitly not in this change):** the FastAPI gateway; any agent definition (Triage, Chat, Magentic, …); any MAF dependency; any channel adapter; any MCP server; any Cosmos / AI Search / Service Bus / Blob / Key Vault SDK call; any Bicep module body; any actual `az` API call. Real Azure dependencies land in the changes that need them.

## Capabilities

### New Capabilities

- `package-skeleton`: the importable `azureclaw` Python package, its config model, the unified Azure credential factory, and the local-test seam they enable

### Modified Capabilities

- `repository-foundation`: the `Python project conventions` requirement is extended to require a passing `pytest -m local` suite with at least one test (the previous bootstrap left the test suite empty by design)

## Impact

- **Affected systems:** local working tree only; no GitHub repo settings change; no Azure resource is touched
- **Affected dependencies:** `pyproject.toml` gains `pydantic`, `pydantic-settings`, `pyyaml`, `azure-identity` as runtime dependencies; the `dev` optional extras already declared in the bootstrap are unchanged
- **Affected APIs:** introduces the public surface `azureclaw.AzureClawConfig`, `azureclaw.azure.credential.build_credential`, plus the type aliases reachable from them
- **Affected docs:** none (the README's "Getting started" section already says `uv sync && uv run pytest -m local`; this change makes that command actually work)
- **Reversibility:** fully reversible — revert the PR; nothing outside the repo changes
