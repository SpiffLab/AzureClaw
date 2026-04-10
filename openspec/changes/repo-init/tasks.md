## 1. Local working tree

- [x] 1.1 Create `C:\Users\calving\Projects\Claude\AzureClaw` and `git init -b main`
- [x] 1.2 Verify Node 20+ and `gh` CLI are installed (install via winget if missing)

## 2. Foundational repo files

- [x] 2.1 Write `README.md` with project summary, status, architecture-at-a-glance table, and contributing instructions
- [x] 2.2 Write `LICENSE` (MIT)
- [x] 2.3 Write `.gitignore` covering Python, Node, OS files, editors, Azure/`azd` artifacts, secrets, and local SQLite databases
- [x] 2.4 Write `.gitattributes` with line-ending normalization for shell/Python/YAML/Bicep (LF) and Windows scripts (CRLF)
- [x] 2.5 Write `pyproject.toml` with Python 3.13 requirement, ruff/pyright/pytest configuration, `local`/`azure`/`hybrid`/`slow` markers, and an empty `dependencies = []` (real deps land in later changes)
- [x] 2.6 Write `config.example.yaml` documenting providers, embeddings, memory, channels, tools, safety, observability, hybrid, and a2a sections

## 3. Dev container

- [x] 3.1 Write `.devcontainer/devcontainer.json` pinning Python 3.13, Node 20, az CLI, azd, Bicep, and the standard VS Code extension set

## 4. GitHub metadata

- [x] 4.1 Write `.github/CODEOWNERS` listing the maintainer as the default owner with extra coverage on `openspec/`, `infra/`, `azureclaw-bridge/`, and the release/what-if workflows
- [x] 4.2 Write `.github/pull_request_template.md` linking PRs back to their OpenSpec change and including the standard test-plan checklist
- [x] 4.3 Write `.github/ISSUE_TEMPLATE/bug.md`
- [x] 4.4 Write `.github/ISSUE_TEMPLATE/change.md` mirroring the OpenSpec proposal structure

## 5. CI workflows

- [x] 5.1 Write `.github/workflows/ci.yml` with three jobs: `ci/lint` (ruff check + ruff format --check + pyright), `ci/test` (`pytest -m local`), `ci/bicep-validate` (`bicep build` for every `infra/**/*.bicep`, no-op when no files exist)
- [x] 5.2 Write `.github/workflows/bicep-what-if.yml` that runs `az deployment sub what-if` against the dev subscription on PRs touching `infra/`, falls back to a no-op if `AZURE_DEV_SUBSCRIPTION_ID` is unset, and posts the diff as a PR comment when it runs
- [x] 5.3 Write `.github/workflows/release.yml` as a manual `workflow_dispatch` workflow that requires `environment` + `confirm` inputs, gates on the `<env>-deploy` GitHub environment, includes a guard step that fails fast if `infra/main.bicep` is missing, and runs `azd provision` then `azd deploy`

## 6. OpenSpec scaffolding

- [x] 6.1 Run `npx -y @fission-ai/openspec init --tools claude,github-copilot --force`
- [x] 6.2 Verify `openspec/`, `openspec/specs/`, `openspec/changes/`, `openspec/config.yaml`, `.claude/commands/opsx/`, and `.github/prompts/opsx-*.prompt.md` exist
- [x] 6.3 Replace the default `openspec/config.yaml` with a populated `context:` field that captures AzureClaw's core architectural decisions (migrated from the approved plan) and per-artifact `rules:` for proposal/design/specs/tasks
- [x] 6.4 Run `npx -y @fission-ai/openspec new change repo-init` to create the change folder
- [x] 6.5 Write `openspec/changes/repo-init/proposal.md`
- [x] 6.6 Write `openspec/changes/repo-init/specs/repository-foundation/spec.md` with all eight requirements from the proposal
- [x] 6.7 Write `openspec/changes/repo-init/design.md` covering the eight key decisions and their rationale
- [x] 6.8 Write `openspec/changes/repo-init/tasks.md` (this file)

## 7. Empty package directories

- [x] 7.1 Create `src/azureclaw/.gitkeep`
- [x] 7.2 Create `azureclaw-bridge/.gitkeep`
- [x] 7.3 Create `infra/.gitkeep`
- [x] 7.4 Create `tests/.gitkeep`
- [x] 7.5 Create `docs/.gitkeep`

## 8. First commit and GitHub push

- [ ] 8.1 `git add .` and `git commit -m "chore: bootstrap AzureClaw repo + OpenSpec scaffolding"`
- [ ] 8.2 Run `gh auth login` interactively (one-time, requires user)
- [ ] 8.3 `gh repo create AzureClaw --public --source=. --remote=origin --push --description "Azure-native, Microsoft Agent Framework re-imagining of OpenClaw"`
- [ ] 8.4 Verify the push landed by visiting the repo URL `gh repo view --web`

## 9. Branch protection

- [ ] 9.1 Apply branch protection on `main` via `gh api PUT /repos/<owner>/AzureClaw/branches/main/protection` requiring 1 PR review, the `ci/lint` + `ci/test` + `ci/bicep-validate` status checks, and enforce-admins
- [ ] 9.2 Create the `develop` branch and push it
- [ ] 9.3 Verify branch protection by attempting `git push origin main` from a local commit and confirming GitHub rejects it

## 10. Validation

- [ ] 10.1 Run `npx -y @fission-ai/openspec validate repo-init` and confirm the change passes
- [ ] 10.2 Run `npx -y @fission-ai/openspec status` and confirm the `repo-init` change shows all artifacts as `done`
- [ ] 10.3 Open the GitHub repo in a browser and confirm the README, license, and OpenSpec config render correctly
