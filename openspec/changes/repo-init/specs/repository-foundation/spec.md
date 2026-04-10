## ADDED Requirements

### Requirement: Repository structure
The AzureClaw repository SHALL contain a fixed top-level layout that every subsequent change inherits, consisting of `openspec/`, `src/azureclaw/`, `azureclaw-bridge/`, `infra/`, `tests/`, `docs/`, `.devcontainer/`, and `.github/` directories, plus the foundational files `README.md`, `LICENSE`, `.gitignore`, `.gitattributes`, `pyproject.toml`, and `config.example.yaml`.

#### Scenario: Bootstrap commit contains the canonical layout
- **WHEN** a contributor clones the repository immediately after the `repo-init` change is merged
- **THEN** all directories listed above exist (with `.gitkeep` placeholders where empty)
- **AND** the foundational files exist at the repository root

#### Scenario: Empty package directories are tracked
- **WHEN** `git ls-files` is run against the bootstrap commit
- **THEN** each empty package directory contains a `.gitkeep` file so the directory is tracked

### Requirement: Python project conventions
The repository SHALL declare Python 3.13 as the minimum supported version and configure ruff (lint + format), pyright (strict type checking), and pytest (with `local`, `azure`, `hybrid`, and `slow` markers) via `pyproject.toml`.

#### Scenario: Tooling versions are pinned in pyproject.toml
- **WHEN** a contributor opens `pyproject.toml`
- **THEN** `requires-python = ">=3.13"` is set
- **AND** `[tool.ruff]`, `[tool.pyright]`, and `[tool.pytest.ini_options]` sections are present
- **AND** the `local`, `azure`, `hybrid`, and `slow` pytest markers are declared

#### Scenario: The package directory is reachable to the build backend
- **WHEN** `uv build` (or any PEP-517 builder) inspects `pyproject.toml`
- **THEN** the `[tool.hatch.build.targets.wheel]` configuration points at `src/azureclaw`

### Requirement: Reproducible developer environment
The repository SHALL provide a `.devcontainer/devcontainer.json` that pins Python 3.13, Node 20+, the Azure CLI, `azd`, and Bicep, and installs the standard VS Code extension set (Python, Pylance, Ruff, Bicep, Docker, Azure Developer CLI, GitHub Actions, TOML, YAML).

#### Scenario: Dev container builds without prompts
- **WHEN** a contributor opens the repository in VS Code with the Dev Containers extension
- **THEN** the container builds using the pinned base image and features
- **AND** all listed VS Code extensions are installed automatically
- **AND** `python --version` reports 3.13.x and `node --version` reports 20.x or newer

### Requirement: CI gates on every PR
The repository SHALL run three required status checks on every pull request to `main` or `develop`: `ci/lint` (ruff check + ruff format --check + pyright), `ci/test` (`pytest -m local` against the SQLite/in-memory fallbacks), and `ci/bicep-validate` (`bicep build` for every file under `infra/**/*.bicep`).

#### Scenario: Lint check runs on every PR
- **WHEN** a pull request is opened against `main` or `develop`
- **THEN** the `ci/lint` job runs and fails the PR if ruff or pyright reports any error

#### Scenario: Test check runs on every PR without Azure credentials
- **WHEN** a pull request is opened against `main` or `develop`
- **THEN** the `ci/test` job runs `pytest -m local` and fails the PR if any test fails
- **AND** the job does not require any Azure credentials or secrets

#### Scenario: Bicep validate check runs on every PR
- **WHEN** a pull request is opened against `main` or `develop`
- **THEN** the `ci/bicep-validate` job iterates over `infra/**/*.bicep` and runs `bicep build` against each file
- **AND** the job passes silently if `infra/` contains no `.bicep` files yet

### Requirement: Bicep what-if previews on infra PRs
When a PR touches files under `infra/`, the repository SHALL run `az deployment sub what-if` against the configured dev subscription and post the change-set diff as a PR comment. Until the dev subscription is configured, the workflow SHALL fall back to a no-op so external contributors are not blocked.

#### Scenario: What-if posts a PR comment when subscription is configured
- **WHEN** a PR modifies a file under `infra/` and the `AZURE_DEV_SUBSCRIPTION_ID` repository variable is set
- **THEN** the workflow runs `az deployment sub what-if` and posts the output as a PR comment

#### Scenario: What-if is a no-op when subscription is not configured
- **WHEN** a PR modifies a file under `infra/` and `AZURE_DEV_SUBSCRIPTION_ID` is empty
- **THEN** the workflow exits successfully without invoking the Azure CLI

### Requirement: Manual gated deployment
The repository SHALL only deploy to Azure via a `release` workflow that requires `workflow_dispatch`, an environment-specific required reviewer (`dev-deploy` or `prod-deploy`), and a confirmation input that matches the chosen environment name. The workflow SHALL include a guard step that fails fast if `infra/main.bicep` does not exist.

#### Scenario: Release workflow refuses to run before infra exists
- **WHEN** a maintainer triggers the `release` workflow before `infra/main.bicep` has been committed
- **THEN** the guard step fails with a clear error and `azd up` is not invoked

#### Scenario: Release workflow requires environment confirmation
- **WHEN** a maintainer triggers the `release` workflow with `environment=dev` and `confirm=prod`
- **THEN** the deploy job is skipped because the inputs do not match

### Requirement: Secret hygiene
The repository SHALL NOT contain any API keys, tokens, certificates, or other secrets in source. The `.gitignore` SHALL exclude `.env*` (except `.env.example`), `*.pem`, `*.key`, `*.pfx`, `*.crt`, `*.p12`, `secrets/`, and `.secrets/`.

#### Scenario: gitignore excludes credential file patterns
- **WHEN** a contributor inspects `.gitignore`
- **THEN** patterns matching `.env`, `*.pem`, `*.key`, `*.pfx`, `*.crt`, `*.p12`, `secrets/`, and `.secrets/` are present

#### Scenario: Bootstrap commit contains no secret files
- **WHEN** `git ls-files` is run against the bootstrap commit
- **THEN** no file matches the patterns above

### Requirement: OpenSpec workflow is the source of truth
The repository SHALL use OpenSpec (Fission-AI) as the spec-driven development workflow. `openspec/config.yaml` SHALL contain the architectural `context:` for AzureClaw. Every meaningful change SHALL land as an `openspec/changes/<name>/` folder reviewed via PR before code is written.

#### Scenario: OpenSpec scaffolding exists after init
- **WHEN** a contributor clones the bootstrap commit
- **THEN** `openspec/config.yaml`, `openspec/specs/`, `openspec/changes/`, and `.claude/commands/opsx/` exist
- **AND** `openspec/config.yaml` has a non-empty `context:` field describing AzureClaw's architecture

#### Scenario: The repo-init change is itself an OpenSpec change
- **WHEN** a contributor inspects `openspec/changes/`
- **THEN** the `repo-init/` folder exists with `proposal.md`, `design.md`, `tasks.md`, and `specs/repository-foundation/spec.md`

### Requirement: Branch protection on main
The repository SHALL configure branch protection on `main` that requires at least 1 approving PR review, requires the `ci/lint`, `ci/test`, and `ci/bicep-validate` status checks to pass, enforces the rules for administrators, and disallows force pushes.

#### Scenario: Direct push to main is rejected
- **WHEN** any contributor attempts `git push origin main` from a local branch without going through a PR
- **THEN** GitHub rejects the push with a branch-protection error

#### Scenario: PR cannot merge with failing CI
- **WHEN** a pull request to `main` has any of `ci/lint`, `ci/test`, or `ci/bicep-validate` failing
- **THEN** the merge button is disabled until those checks pass
