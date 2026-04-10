## Context

AzureClaw is greenfield. This change exists because the approved plan (`~/.claude/plans/bubbly-baking-crescent.md`) explicitly gates every later activity behind "the repo exists, OpenSpec is initialized, and CI is green." The work here is structural rather than behavioral: no Python is written, no Azure resource is created, and no third-party service is wired up. The artifacts are all metadata, conventions, and CI plumbing.

The maintainer's environment is Windows 11 with git-bash, Git for Windows, Node.js 24 LTS (just installed), GitHub CLI 2.89 (just installed), and Claude Code as the primary AI assistant. The repo will live on disk at `C:\Users\calving\Projects\Claude\AzureClaw` and on GitHub under the maintainer's personal account at `github.com/<user>/AzureClaw`. The repository will be **public** from creation.

## Goals / Non-Goals

**Goals:**

- Lock in the structural conventions (Python tooling versions, CI gate names, OpenSpec layout, branch protection rules) so no later change has to retrofit them.
- Make the deploy path impossible to fire accidentally — both through workflow design (manual dispatch + environment + confirm input) and through a guard step that fails fast if `infra/main.bicep` does not yet exist.
- Make the local-dev path runnable on day one without any Azure access. `pytest -m local` is the canonical "this works on my machine" check and runs in CI on every PR.
- Establish OpenSpec as the source of truth so that the very first PR can be reviewed against `openspec/changes/repo-init/`.

**Non-Goals:**

- Writing any Python implementation code. Even a `__init__.py` for `src/azureclaw/` is out of scope (a `.gitkeep` is enough).
- Writing any Bicep module body. `infra/` is empty in this change; the first Bicep modules land in change #3 (`azure-infra-bootstrap`).
- Provisioning any Azure resources. The release workflow is committed but inert.
- Declaring any runtime dependencies in `pyproject.toml`. Dependencies land alongside the modules that need them, in their own changes.
- Adding any channel adapter SDK, Microsoft Agent Framework dependency, or external service integration.
- Setting up federated identity for the Azure subscription (that is part of `azure-infra-bootstrap`).

## Decisions

### Decision: Use OpenSpec for spec-driven development instead of plain Markdown design docs

**Why:** OpenSpec gives us a structured artifact set (`proposal.md` + per-capability `specs/` + `design.md` + `tasks.md`), automatic verification via `openspec validate`, and slash-command integration with Claude Code and GitHub Copilot. The alternative — ad-hoc design docs — has no enforcement of spec/code drift. OpenSpec's `openspec/specs/` accumulates the unified living spec as changes land, which gives us a single source of truth that survives across conversations.

**Alternatives considered:** plain `docs/` markdown (rejected: no drift detection); GitHub Issues + PRs only (rejected: scattered, not queryable as a unit); Architecture Decision Records (ADRs) (considered as a complement; ADRs may still appear under `docs/` for cross-cutting historical decisions).

### Decision: Microsoft Bicep instead of Terraform for infrastructure-as-code

**Why:** AzureClaw is Azure-only by design. Bicep is the first-class Microsoft IaC language for Azure, has the best ARM coverage, integrates with `azd up`, is supported by VS Code's Bicep extension, and has `bicep what-if` for PR review. Terraform would mean a non-Microsoft tool when there is a perfectly good Microsoft one.

**Alternatives considered:** Terraform with the AzureRM provider (rejected for the reason above); raw ARM JSON (rejected: unreadable); Pulumi in Python (interesting because it would unify the language, but has weaker ARM coverage and non-Microsoft).

### Decision: `uv` as the Python package manager

**Why:** `uv` is the fastest, most reproducible Python package manager available, has first-class lockfile support, and is a single static binary that the dev container and CI can install in one step. It pairs cleanly with PEP 517 build backends (`hatchling` here).

**Alternatives considered:** `pip-tools` (slower, less ergonomic); `poetry` (heavier, slower lockfile resolution, less PEP 517-native); `pdm` (good but smaller community).

### Decision: `ruff` for both linting and formatting; `pyright` (strict) for type checking

**Why:** `ruff` is dramatically faster than the `flake8 + black + isort` stack and replaces all three. `pyright` strict mode is the default for any new MAF/Azure SDK work because both ecosystems are heavily typed. Putting these in CI from day one means no later change has to pay the cost of fixing accumulated type errors.

**Alternatives considered:** `mypy` (rejected: pyright has better Azure SDK type inference and is what MAF's own examples use); `black + isort + flake8` (rejected: ruff replaces all three at 50-100× the speed).

### Decision: CI gate names are stable and load-bearing

**Why:** Branch protection on `main` references the literal status check names `ci/lint`, `ci/test`, `ci/bicep-validate`. Renaming any of them later would silently break branch protection (PRs would merge without the check). Locking these names in the bootstrap and treating them as a contract avoids that footgun.

**Alternatives considered:** generic names like `ci`/`test` (rejected: less self-documenting); using GitHub's "required checks" wildcards (rejected: less explicit).

### Decision: Release workflow is committed but inert

**Why:** Committing the release workflow with a guard step (`if [ ! -f infra/main.bicep ]; then exit 1; fi`) does two things at once: it documents how deploys are intended to work, and it makes accidental triggering harmless. The alternative — adding the workflow only when we're ready to deploy — would mean the deploy path is invisible during reviews of changes 1-15.

**Alternatives considered:** add the release workflow in `azure-infra-bootstrap` (rejected: hides the deploy contract); use a separate "deploy" repo (rejected: splits review surface).

### Decision: `bicep-what-if` is a no-op when the dev subscription is not configured

**Why:** External contributors should be able to open PRs without an Azure subscription. The workflow checks for the `AZURE_DEV_SUBSCRIPTION_ID` repository variable; if absent, it returns success without invoking the Azure CLI. Maintainers configure the variable + federated credentials separately as part of `azure-infra-bootstrap`.

**Alternatives considered:** require all contributors to have Azure access (rejected: kills outside contribution); skip the workflow entirely until later (rejected: leaves a gap in the review story).

### Decision: Branch protection requires only 1 approval, not 2

**Why:** AzureClaw is a single-maintainer repo at the moment. Requiring 2 reviews would block all merges. We can raise the count later via `gh api` once there are multiple committers; the contract is "at least 1," not "exactly 1."

### Decision: The repo is **public** from day one

**Why:** The maintainer chose public during the planning conversation, overriding the original "private until first smoke passes" default. Public from day one lets the OpenSpec workflow be reviewed openly, accepts external feedback earlier, and means the (eventual) `gh api` calls for branch protection use the public-repo endpoints. The downside — the repo is visible while still empty — is minimal because the README and OpenSpec config make the early-stage status obvious.

## Risks / Trade-offs

- **Risk:** OpenSpec is a relatively young tool; its CLI surface or schema may change. → **Mitigation:** pin a specific OpenSpec version in CI when we add the OpenSpec validate job in a later change; treat the `openspec/` directory as load-bearing and bring schema-migration changes into their own OpenSpec proposals.

- **Risk:** Branch protection configured via `gh api` can drift from intent over time. → **Mitigation:** check the protection JSON into `docs/branch-protection.json` in a follow-up change so it can be diff-reviewed if it's ever changed manually.

- **Risk:** The `release.yml` guard step ("`infra/main.bicep` must exist") protects against the *current* failure mode but not against deploying broken Bicep. → **Mitigation:** acceptable for repo-init; the `bicep-what-if` workflow + the manual dev-deploy reviewer cover that gap once `azure-infra-bootstrap` lands.

- **Risk:** A contributor running on Windows without WSL may struggle with the CRLF/LF normalization. → **Mitigation:** `.gitattributes` is comprehensive (forces LF for shell, Python, YAML, Bicep, etc.; CRLF for `.bat`/`.cmd`/`.ps1`); the dev container is Linux-based and avoids the issue entirely.

- **Risk:** The `pyproject.toml` declares `requires-python = ">=3.13"` but the dev container image is `python:1-3.13-bookworm`; if a contributor uses a system Python it may be older. → **Mitigation:** acceptable; `uv sync` enforces the minimum and the README points at the dev container as the supported path.

- **Risk:** The repo is **public** from day one. Anything pushed (including commit messages and PR descriptions) is world-readable. → **Mitigation:** the bootstrap commit contains no secrets and no sensitive context. `.gitignore` excludes credential file patterns. The `gh api` branch-protection call uses no secrets (only the maintainer's gh auth token, which never enters the repo).

## Migration Plan

This is the bootstrap change — there is nothing to migrate from. The post-merge state is:

1. The GitHub repo `<user>/AzureClaw` exists and is **public**.
2. `main` has branch protection.
3. `develop` exists as a working branch.
4. Local working tree at `C:\Users\calving\Projects\Claude\AzureClaw` is a clean checkout of the bootstrap commit.

**Rollback:** delete the GitHub repo (`gh repo delete <user>/AzureClaw --yes`) and the local working tree. Because no Azure resources or external services were touched, rollback is fully reversible and leaves no trace.

## Open Questions

- Should `develop` be the default merge target instead of `main`? (Deferred: keep `main` as default for now; we can swap defaults in a later change without disruption.)
- Do we want to enable Dependabot from day one for `pyproject.toml` and the GitHub Actions versions? (Deferred to a small follow-up change after `bootstrap-skeleton` lands real dependencies.)
- Should the OpenSpec slash commands be installed only for Claude Code, only for Copilot, or both? **Decided in this change**: both, via `openspec init --tools claude,github-copilot`.
