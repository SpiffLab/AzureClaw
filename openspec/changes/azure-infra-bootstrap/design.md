## Context

The bootstrap commit and the `bootstrap-skeleton` change established AzureClaw's local-dev story (Pydantic config model, hermetic credential factory, passing local tests). This change is the mirror for the cloud side: it commits a complete Bicep blueprint of every Azure resource AzureClaw will use, plus the `azd` project manifest that ties them together. **No resource is created in any Azure subscription by this PR.** Provisioning is the job of the much later `first-deploy-dev` change (#23) which runs `azd up` from a manual `workflow_dispatch` against a `dev-deploy` GitHub environment with a required reviewer.

The purpose of landing the Bicep this early — even though it cannot be deployed yet — is twofold:

1. The `ci/bicep-validate` gate becomes load-bearing the moment this PR merges. Every later change that touches `infra/` is compile-checked against real ARM schemas during PR review.
2. `bicep what-if` becomes meaningful for review. As soon as the dev subscription is wired (a separate one-off operator task), `bicep-what-if.yml` posts a PR-comment diff for every change-set that touches `infra/`.

The deploy gate stays where it is. `release.yml` already has a guard step that fails fast if `infra/main.bicep` is missing; that file now exists, so the guard passes — but the workflow still requires `workflow_dispatch`, environment approval, and a confirmation input that matches the environment name. Three independent gates against accidental deploys.

## Goals / Non-Goals

**Goals:**

- Ship a complete, compiling Bicep blueprint of every Azure service named in `openspec/config.yaml`'s architectural context. If a service is in the `Concept mapping` of the project context, it has a module here.
- Make `azd up` *runnable* (not run!) from a contributor's machine by providing a valid `azure.yaml` and `infra/parameters.dev.bicepparam`.
- Establish a stable module boundary so each later change can extend exactly one module without sprawling across the infra tree.
- Compile cleanly under `bicep build` for every file under `infra/`. Zero warnings under the strict linter is a stretch goal but not required for this change.
- Use Bicep's resource functions (`listKeys`, `reference`) and managed identity assignments instead of any literal secret in source.

**Non-Goals:**

- Running `azd up`, `azd provision`, `az deployment sub create`, or any other call that would create an Azure resource.
- Setting up the federated credentials / OIDC trust between GitHub and an Azure subscription. That's a one-off operator task that lives outside this repo (it's a click-through in the Azure portal or a `gh secret set` + portal trust setup). This change documents what variables the workflows need but does not provision them.
- Application code that *uses* any of these resources. Each service binding lands with the OpenSpec change that owns it: `gateway-and-webhooks` wires Container Apps, `memory-cosmos-aisearch` wires Cosmos + AI Search, `llm-failover-middleware` wires Foundry, etc.
- Scaffolding ALL the parameters files for ALL the environments. Only `parameters.dev.bicepparam` is shipped; `parameters.prod.bicepparam` lands when the prod subscription is wired (much later).
- Touching the Hybrid Relay or per-site Bicep modules — those are owned by `hybrid-relay-infra` (#16). This change is about the *core* Azure footprint.
- Touching the Durable Functions Function App for cron — that's owned by `durable-functions-cron` (#11).

## Decisions

### Decision: Subscription-scoped `main.bicep` that creates the resource group itself

**Why:** Two common patterns in `azd` projects: (a) target the resource group scope and assume the operator created it, or (b) target the subscription scope and let `main.bicep` create the group. Pattern (b) is cleaner for greenfield projects because there is exactly one entrypoint and `azd up` becomes a single command. The operator does not need to remember to create a group first.

**Alternatives considered:** target the resource group scope with `azd` creating the group implicitly (rejected: less explicit, harder to read in PRs); target a management group scope (rejected: overkill for a single-tenant project).

### Decision: One Bicep module per service, each ~50-100 lines

**Why:** Module boundaries match the OpenSpec change boundaries. When `memory-cosmos-aisearch` lands in change #9 it touches exactly `cosmos.bicep` and `aisearch.bicep`. When `approval-loop-servicebus` lands it touches exactly `servicebus.bicep`. PR review surface stays small and focused.

**Alternatives considered:** one mega-module per resource type (rejected: PR review surface explodes); one module per *change* (rejected: services like Cosmos are touched by multiple changes); flatten everything into `main.bicep` (rejected: 800-line files do not review well).

### Decision: Sample / placeholder values, not real subscription IDs

**Why:** This PR is reviewable by anyone, including external contributors. Real subscription ids, tenant ids, or resource names would either leak operator-private information or land as values that no one else can use. `parameters.dev.bicepparam` therefore uses the literal `<your-dev-subscription>` and `<your-dev-rg-prefix>` style placeholders that the operator overrides at `azd up` time via environment variables (`AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, `AZURE_ENV_NAME`).

**Alternatives considered:** ship a `parameters.dev.bicepparam` with the real values committed (rejected: leaks internal details, breaks for other contributors); commit a `.gitignore`d `parameters.dev.bicepparam` and a `.bicepparam.example` (rejected: extra mental overhead, harder to review).

### Decision: Cosmos containers and AI Search index schema are committed in this change, not later

**Why:** The container partition keys (`/session_id`, `/site_id`) and the AI Search index schema (`embedding` field with `dimensions: 3072` matching `text-embedding-3-large`) are part of the Azure surface, not the application code. They live in Bicep so they are version-controlled and what-if-diff-able. Alternative approaches (creating containers from application code on first run) are anti-patterns: they hide schema changes from PR review and create boot-time race conditions.

**Alternatives considered:** create containers lazily from `azureclaw.memory.cosmos_thread_store` on first connect (rejected: hides schema in code, cannot be reviewed in `bicep what-if`); use Cosmos's autoscale + serverless without specific containers (rejected: every container needs an explicit partition key, this isn't optional).

### Decision: Foundry deploys both `gpt-5.4-mini` (chat) and `text-embedding-3-large` (embedding) in this change

**Why:** Both are "single source of truth" decisions. The chat model is what `Triage`, `Chat`, and the Magentic team will all default to (per `openspec/config.yaml`'s context). The embedding model is what `aisearch.bicep`'s `embedding.dimensions = 3072` is calibrated for. Splitting them across two changes would create a window where the AI Search index expects 3072-dim vectors but no embedding model has been deployed.

**Alternatives considered:** ship Foundry empty and add deployments in `llm-failover-middleware` and `memory-cosmos-aisearch` separately (rejected: split-brain risk on the embedding dimension contract); use Foundry's `default` deployments (rejected: not actually a thing in Foundry's API).

### Decision: Container Apps gateway is provisioned with a placeholder image

**Why:** `containerapps.bicep` needs *some* container image to declare the Container App resource at all. The placeholder `mcr.microsoft.com/k8se/quickstart:latest` is a tiny Microsoft-published "hello world" image used by the official ACA quickstart. It lets `bicep build` and `bicep what-if` succeed and lets the operator stand up a runnable (but useless) gateway during early bring-up. The real image lands with the `gateway-and-webhooks` change after the gateway code exists and a CI build pushes a tagged image to ACR.

**Alternatives considered:** ship `containerapps.bicep` with no Container App resource at all and add it in a later change (rejected: every later infra change becomes "edit two modules"); use `nginx:latest` (rejected: pulled from Docker Hub, rate-limited, not a Microsoft source).

### Decision: ACR is part of this change, not a separate one

**Why:** Container Apps cannot pull from ACR without a managed identity role assignment, and that role assignment is most cleanly declared in the same change that creates both resources. Splitting them creates an awkward intermediate state where `containerapps.bicep` references a registry that does not yet exist.

**Alternatives considered:** put ACR in a separate `acr-bootstrap` change (rejected: see above); put ACR in `containerapps.bicep` directly (rejected: muddles the module boundary).

### Decision: No federated credential / OIDC trust setup in this change

**Why:** Setting up the GitHub-to-Azure federated credential is a one-time operator action that requires (a) creating an Entra ID app registration, (b) creating a federated credential whose subject matches the repo and environment, and (c) granting that app `Contributor` on the dev subscription. None of this is reviewable IaC — it's a click-through. We document the required GitHub variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, `AZURE_DEV_SUBSCRIPTION_ID`, `AZURE_DEV_LOCATION`, `AZURE_DEV_CLIENT_ID`) in the workflow files but do not provision them.

**Alternatives considered:** include a Bicep module that creates the Entra app + federated credential (rejected: management-group-scoped; requires elevated permissions; outside `azd`'s normal flow).

### Decision: `azure.yaml` is minimal — one project, one service

**Why:** `azd` accepts a wide range of `azure.yaml` schemas, but for a single-service project the smallest valid file is the most readable. As more services land (the browser MCP sidecar, Durable Functions for cron, etc.), this file grows naturally.

## Risks / Trade-offs

- **Risk:** A Bicep API version pinned in this change is deprecated by the time `first-deploy-dev` actually runs. → **Mitigation:** use `@2024-*` API versions, which Azure supports for at least 12 months from release. The `bicep-what-if` job will catch deprecations on every PR; we update versions as the linter flags them.

- **Risk:** The Cosmos partition key `/session_id` does not scale well if a single session generates millions of items (one container in AzureClaw is the `audit` log). → **Mitigation:** acceptable for the dev environment, where each session is a small chat. The `audit` container will get a hierarchical partition key in a follow-up change once we have real usage data.

- **Risk:** AI Search vector dimensions are pinned to 3072 to match `text-embedding-3-large`. If a future change swaps the embedding model, the index needs to be rebuilt. → **Mitigation:** acceptable; the swap is a deliberate decision, not a quiet drift, and the linkage between `foundry.bicep` (model deployment) and `aisearch.bicep` (vector dimensions) is documented in the design.

- **Risk:** The `containerapps.bicep` placeholder image is a Microsoft sample that will eventually be deprecated or moved. → **Mitigation:** the image is overwritten by the first real deploy of `gateway-and-webhooks`. If the placeholder URL goes 404 in the meantime, `bicep build` still succeeds (it doesn't pull the image at compile time).

- **Risk:** `parameters.dev.bicepparam` ships with placeholder values; an operator who copies it as-is and runs `azd up` gets a deploy failure rather than a clean error. → **Mitigation:** the placeholders are obvious (`<your-dev-subscription>` style strings) and `azd` will report a clear "subscription not found" error. Acceptable trade-off for not committing real values.

- **Risk:** Foundry resources have regional availability constraints that may not match the operator's chosen region. → **Mitigation:** `parameters.dev.bicepparam` defaults `location = 'eastus2'` (one of the broadest Foundry regions). The operator overrides via `AZURE_LOCATION` if they need a different region.

- **Risk:** The PR diff is large (10 Bicep modules + main + 2 parameters files + azure.yaml ≈ ~600 lines of new IaC). → **Mitigation:** acceptable; each module is small (~50-100 lines), the spec scenarios make the requirements explicit, and `bicep build` provides ground-truth validation. PR reviewers can check each module against its named requirement in the spec.

## Migration Plan

This is greenfield infrastructure code. There is no migration. The post-merge state is:

1. Every Bicep module under `infra/modules/` exists and compiles.
2. `infra/main.bicep` compiles and would deploy a complete AzureClaw footprint if `azd up` were run.
3. `azure.yaml` exists at the repo root and `azd config get` recognizes the project.
4. `ci/bicep-validate` runs against the new files on every PR.
5. `bicep-what-if` workflow's "skip when missing" branch is removed (the file is guaranteed to exist).
6. The `release.yml` guard step that previously failed because `infra/main.bicep` was missing now passes (but the workflow still requires manual dispatch, environment approval, and confirmation input).

**Rollback:** revert the PR. The `ci/bicep-validate` job returns to its no-op behavior; `release.yml`'s guard reverts to failing fast. No external state is affected.

## Open Questions

- Should we create a separate `dev` and `prod` resource group with different naming (`azureclaw-dev-rg` vs `azureclaw-prod-rg`), or use the same group with different `azd env` names? → **Decided in this change:** different groups, naming is `azureclaw-${environment}-rg`, controlled by the `environment` parameter. Easy to change later if it proves wrong.

- Should the Bicep modules use the new `userAssignedIdentities` model or stick with system-assigned managed identities? → **Decided in this change:** system-assigned for everything in this round. User-assigned identity is only needed when multiple resources need to share an identity, which isn't a constraint AzureClaw has yet. Trivial to swap later.

- Should we validate the spec scenarios with a Bicep linter beyond `bicep build`? → **Deferred:** the strict Bicep linter (`bicep lint`) catches more than `bicep build`, but it also flags many warnings that are fine in greenfield code. We'll add a separate `ci/bicep-lint` gate (without strict failure) in a follow-up change once the modules have stabilized.
