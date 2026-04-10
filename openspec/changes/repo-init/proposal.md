## Why

AzureClaw needs a versioned, reviewable, GitHub-hosted home before any code is written or any Azure resource is provisioned. The first commit must lock in the conventions every subsequent change inherits — Python tooling, CI gates, OpenSpec workflow, dev container, license, branch protection — so that every PR after this one starts on a known foundation rather than retrofitting one. The hard rule is that nothing gets deployed to Azure until the repo exists, OpenSpec is initialized, and CI is green on a PR.

## What Changes

- Create the GitHub repository `AzureClaw` under the maintainer's personal account, **public**, with the description "Azure-native, Microsoft Agent Framework re-imagining of OpenClaw"
- Add foundational repo files: `README.md`, `LICENSE` (MIT), `.gitignore`, `.gitattributes`, `pyproject.toml`, `config.example.yaml`
- Add `.devcontainer/devcontainer.json` pinning Python 3.13, Node 20+, the Azure CLI, `azd`, Bicep, and the standard VS Code extension set
- Add GitHub metadata: `.github/CODEOWNERS`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug.md`, `.github/ISSUE_TEMPLATE/change.md`
- Add CI workflows: `.github/workflows/ci.yml` (lint + test + bicep-validate), `.github/workflows/bicep-what-if.yml` (PR diff against dev subscription, no-op until subscription is wired), `.github/workflows/release.yml` (manual `azd up`, gated behind a deploy environment with required reviewer and a guard step that fails fast until `infra/main.bicep` exists)
- Initialize OpenSpec via `openspec init --tools claude,github-copilot` and seed `openspec/config.yaml` with the unified architectural context migrated from the approved plan
- Create empty package directories with `.gitkeep` placeholders for `src/azureclaw/`, `azureclaw-bridge/`, `infra/`, `tests/`, `docs/`
- Apply branch protection on `main` requiring 1 PR review and the `ci/lint`, `ci/test`, `ci/bicep-validate` status checks

**Non-goals (explicitly not in this change):** any Python implementation; any Bicep module bodies (the `infra/` directory is empty); any `azd up`, `az deployment`, or other Azure resource creation; any secret writes; any channel adapter wiring; any Microsoft Agent Framework dependency declarations.

## Capabilities

### New Capabilities

- `repository-foundation`: the structural conventions every future AzureClaw change inherits — repo metadata, CI gates, dev environment, OpenSpec workflow, branch protection, deploy gating

### Modified Capabilities

_(none — this is the bootstrap)_

## Impact

- **Affected systems:** GitHub (new repo created, branch protection set), the maintainer's local filesystem (new working tree at `C:\Users\calving\Projects\Claude\AzureClaw`)
- **Affected dependencies:** none (no runtime dependencies declared in this change; `pyproject.toml` lists only the dev extras as a contract for what later changes will install)
- **Affected APIs:** none
- **Affected docs:** the approved plan at `~/.claude/plans/bubbly-baking-crescent.md` becomes the seed for `openspec/config.yaml`'s `context:` field; the plan file itself stays put as historical reference
- **Reversibility:** fully reversible — deleting the repo removes everything; no Azure or external state is modified
