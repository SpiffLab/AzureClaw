## ADDED Requirements

### Requirement: Importable azureclaw package
The repository SHALL contain an installable Python package named `azureclaw` rooted at `src/azureclaw/` that exposes a `__version__` string and is importable from a fresh `uv sync` of `pyproject.toml`.

#### Scenario: Package imports cleanly after uv sync
- **WHEN** a contributor runs `uv sync` followed by `uv run python -c "import azureclaw; print(azureclaw.__version__)"`
- **THEN** the command exits 0 and prints a non-empty version string

#### Scenario: Editable install registers the package
- **WHEN** a contributor runs `uv pip install -e .`
- **THEN** `python -c "import azureclaw"` succeeds in any working directory

### Requirement: Typed configuration model
The package SHALL expose `azureclaw.AzureClawConfig`, a Pydantic v2 model whose fields mirror every top-level section of `config.example.yaml` (`environment`, `providers`, `embeddings`, `memory`, `channels`, `tools`, `safety`, `observability`, `hybrid`, `a2a`), and a classmethod `AzureClawConfig.from_yaml(path)` that loads and validates a YAML file into an instance of the model.

#### Scenario: config.example.yaml parses without validation errors
- **WHEN** `AzureClawConfig.from_yaml(Path("config.example.yaml"))` is called from the repository root
- **THEN** the call returns an `AzureClawConfig` instance
- **AND** no `pydantic.ValidationError` is raised
- **AND** the resulting instance's `environment` field equals `"dev"` (the value declared in `config.example.yaml`)

#### Scenario: Missing required fields fail loudly
- **WHEN** a YAML file is loaded that omits the `environment` key entirely
- **THEN** `AzureClawConfig.from_yaml` either accepts the default `"local"` or raises a `pydantic.ValidationError` — and SHALL NOT silently produce a half-built model

#### Scenario: @kv: secret pointers are preserved as plain strings
- **WHEN** a YAML file contains `api_key: "@kv:anthropic-api-key"`
- **THEN** the parsed model exposes the literal string `"@kv:anthropic-api-key"` on the relevant field
- **AND** no Key Vault network call is made during parsing

### Requirement: Unified credential factory
The package SHALL expose `azureclaw.azure.credential.build_credential(environment)` as the single entry point every Azure-touching module uses to obtain a `TokenCredential`. For `environment` values `"dev"` or `"prod"` it SHALL return an `azure.identity.DefaultAzureCredential`. For `environment="local"` it SHALL return a stub credential whose `get_token()` is callable, makes no network call, and returns a non-empty string token suitable for offline tests.

#### Scenario: Local environment returns a stub
- **WHEN** `build_credential("local")` is called
- **THEN** the returned object has a callable `get_token()` method
- **AND** invoking `get_token("https://example.com/.default")` returns an object with a non-empty `.token` attribute
- **AND** no network connection is opened during the entire sequence

#### Scenario: Production environment returns DefaultAzureCredential
- **WHEN** `build_credential("dev")` or `build_credential("prod")` is called and the `azure.identity` package is installed
- **THEN** the returned object is an instance of `azure.identity.DefaultAzureCredential`

#### Scenario: Local path does not require azure-identity at import time
- **WHEN** the `local` test suite runs in an environment where `azure.identity` is uninstalled
- **THEN** importing `azureclaw.azure.credential` and calling `build_credential("local")` still succeeds

### Requirement: Passing local test suite
The repository SHALL ship at least one test file under `tests/` marked with the `local` pytest marker, and `uv run pytest -m local` SHALL exit 0 against the bootstrap-skeleton change without requiring any Azure credentials, network access, or environment variables beyond what `pyproject.toml` declares.

#### Scenario: pytest -m local exits zero
- **WHEN** a contributor runs `uv sync && uv run pytest -m local` in a fresh checkout of the bootstrap-skeleton change
- **THEN** the command exits 0
- **AND** at least one test is collected and executed
- **AND** no test in the suite makes a real outbound network call

#### Scenario: Test suite runs without Azure credentials
- **WHEN** `pytest -m local` runs in an environment with no `AZURE_*` environment variables, no `~/.azure/` config, and no `az login` state
- **THEN** every collected test still passes

## MODIFIED Requirements

### Requirement: Python project conventions
The repository SHALL declare Python 3.13 as the minimum supported version and configure ruff (lint + format), pyright (strict type checking), and pytest (with `local`, `azure`, `hybrid`, and `slow` markers) via `pyproject.toml`. The repository SHALL include at least one test marked `local`, and `uv run pytest -m local` SHALL exit 0 against every commit on `main`.

#### Scenario: Tooling versions are pinned in pyproject.toml
- **WHEN** a contributor opens `pyproject.toml`
- **THEN** `requires-python = ">=3.13"` is set
- **AND** `[tool.ruff]`, `[tool.pyright]`, and `[tool.pytest.ini_options]` sections are present
- **AND** the `local`, `azure`, `hybrid`, and `slow` pytest markers are declared

#### Scenario: The package directory is reachable to the build backend
- **WHEN** `uv build` (or any PEP-517 builder) inspects `pyproject.toml`
- **THEN** the `[tool.hatch.build.targets.wheel]` configuration points at `src/azureclaw`

#### Scenario: pytest -m local passes on every commit on main
- **WHEN** a commit lands on `main` after this change is merged
- **THEN** the `ci/test` job runs `uv run pytest -m local` and exits 0
