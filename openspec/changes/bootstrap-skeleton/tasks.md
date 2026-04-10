## 1. Dependencies

- [ ] 1.1 Add `pydantic>=2.5,<3` to `pyproject.toml` `[project] dependencies`
- [ ] 1.2 Add `pydantic-settings>=2.5,<3` to `[project] dependencies`
- [ ] 1.3 Add `PyYAML>=6` to `[project] dependencies`
- [ ] 1.4 Add `azure-identity>=1.19,<2` to `[project] dependencies`

## 2. Package skeleton

- [ ] 2.1 Delete `src/azureclaw/.gitkeep`
- [ ] 2.2 Create `src/azureclaw/__init__.py` with a module docstring and `__version__ = "0.0.0"`
- [ ] 2.3 Create `src/azureclaw/azure/__init__.py` (empty subpackage marker, with a one-line docstring)

## 3. Configuration model

- [ ] 3.1 Create `src/azureclaw/config.py` with Pydantic v2 models for every top-level section of `config.example.yaml`: `ProviderConfig`, `EmbeddingsConfig`, `MemoryConfig`, `ChannelsConfig`, `ToolsConfig`, `SafetyConfig`, `ObservabilityConfig`, `HybridConfig`, `A2AConfig`, and the root `AzureClawConfig`
- [ ] 3.2 Use `dict | None = None` for sections whose internal structure is still being designed in later changes (`memory.cosmos`, `memory.ai_search`, `tools.browser`, etc.)
- [ ] 3.3 Add `AzureClawConfig.from_yaml(path: Path) -> AzureClawConfig` classmethod that loads YAML and validates
- [ ] 3.4 Re-export `AzureClawConfig` from `src/azureclaw/__init__.py`

## 4. Credential factory

- [ ] 4.1 Create `src/azureclaw/azure/credential.py` with a `TokenCredentialLike` Protocol declaring `get_token(*scopes: str, **kwargs) -> Token`
- [ ] 4.2 Create a private `_LocalStubCredential` class implementing the protocol; its `get_token()` returns a stub token without any network call
- [ ] 4.3 Implement `build_credential(environment: str) -> TokenCredentialLike` that returns the stub for `"local"` and lazily imports + instantiates `azure.identity.DefaultAzureCredential` for `"dev"` / `"prod"`
- [ ] 4.4 Document the protocol-vs-real-class trade-off in the module docstring

## 5. Test scaffolding

- [ ] 5.1 Delete `tests/.gitkeep`
- [ ] 5.2 Create `tests/__init__.py` (empty)
- [ ] 5.3 Create `tests/conftest.py` (empty for now; one-line docstring explaining purpose)

## 6. Tests

- [ ] 6.1 Create `tests/test_package.py` with a `local`-marked test that imports `azureclaw`, asserts `azureclaw.__version__` is a non-empty string, and asserts `azureclaw.AzureClawConfig` exists
- [ ] 6.2 Create `tests/test_config_loads.py` with a `local`-marked test that calls `AzureClawConfig.from_yaml(Path("config.example.yaml"))` from the repo root and asserts `cfg.environment == "dev"` and the providers list has length 3
- [ ] 6.3 Create `tests/test_credential_local_stub.py` with two `local`-marked tests: (a) `build_credential("local")` returns an object whose `get_token()` returns a non-empty string token; (b) the import of `azureclaw.azure.credential` does not transitively import `azure.identity`
- [ ] 6.4 Use `pytest.mark.local` decorators on every test in this change

## 7. Verification

- [ ] 7.1 Run `uv sync` and confirm dependencies install cleanly
- [ ] 7.2 Run `uv run pytest -m local -v` and confirm every test passes
- [ ] 7.3 Run `uv run ruff check src tests` and confirm clean
- [ ] 7.4 Run `uv run ruff format --check src tests` and confirm clean
- [ ] 7.5 Run `uv run pyright src tests` and confirm clean
- [ ] 7.6 Run `npx -y @fission-ai/openspec validate bootstrap-skeleton` and confirm the change validates

## 8. Commit and PR

- [ ] 8.1 Commit (1) — OpenSpec artifacts only — with message `spec: bootstrap-skeleton — package, config, credential factory, first local tests`
- [ ] 8.2 Commit (2) — implementation — with message `feat: bootstrap-skeleton implementation`
- [ ] 8.3 Push `feature/bootstrap-skeleton` to origin
- [ ] 8.4 Open a PR against `develop` via `gh pr create`, linking it to the OpenSpec change folder
