## Why

AzureClaw is an Azure-first system. Every later OpenSpec change — from the FastAPI gateway to the Magentic research team to the on-prem connector — assumes Azure resources exist (Cosmos DB, AI Search, Key Vault, App Insights, Service Bus, Blob Storage, Container Apps, Container Registry, Foundry, Content Safety). This change lands the Bicep blueprint that *describes* all of those resources, but does not provision any of them. Provisioning is gated to the much later `first-deploy-dev` change (#23 in the queue) that fires `azd up` from a manual `workflow_dispatch` against a dev-deploy GitHub environment with a required reviewer.

The hard rule: **the bicep-validate CI gate becomes meaningful as soon as this change merges**, so every subsequent infra PR gets compile-checked against real ARM schemas. Without this change the `ci/bicep-validate` job is a no-op.

## What Changes

- Add `infra/main.bicep` — a subscription-scoped entrypoint that creates the resource group and invokes every per-service module
- Add `infra/parameters.dev.bicepparam` and `infra/parameters.prod.bicepparam` — the bicepparam files for each environment
- Add per-service Bicep modules under `infra/modules/`:
  - `cosmos.bicep` — Azure Cosmos DB account, database, and `threads` / `checkpoints` / `audit` / `sites` containers (NoSQL API, autoscale, partitioned by `session_id` / `site_id`)
  - `aisearch.bicep` — Azure AI Search service + the `azureclaw-memory` index schema (vector + scalar fields)
  - `keyvault.bicep` — Key Vault + access policy granting the Container Apps managed identity `get`/`list` on secrets
  - `appinsights.bicep` — Log Analytics workspace + Application Insights component
  - `servicebus.bicep` — Service Bus namespace + `approvals` queue
  - `storage.bicep` — Storage account + `canvas` blob container
  - `containerapps.bicep` — Container Apps environment, the gateway app placeholder, and a sidecar container slot for the browser MCP server
  - `acr.bicep` — Azure Container Registry with the ACA managed identity granted `AcrPull`
  - `contentsafety.bicep` — Azure AI Content Safety resource
  - `foundry.bicep` — Azure AI Foundry project + a `gpt-5.4-mini` chat deployment + a `text-embedding-3-large` embedding deployment
- Add `azure.yaml` at the repo root — `azd` project manifest pointing at `infra/main.bicep` and declaring the gateway service
- Update `.github/workflows/bicep-what-if.yml` — remove the "skip if `infra/main.bicep` does not exist" branch (it now always exists). The `if vars.AZURE_DEV_SUBSCRIPTION_ID == ''` no-op branch stays so external contributors are not blocked.
- Update `.github/workflows/release.yml` — the guard step that fails fast when `infra/main.bicep` is missing now becomes load-bearing in the opposite direction (the file exists, so the check passes and the workflow proceeds to the *environment-gated* deploy job, which still requires manual `workflow_dispatch` and a required reviewer)

**Non-goals (explicitly not in this change):** any actual `azd up`, `az deployment sub create`, or any other Azure resource creation; any federated credential / OIDC trust setup between GitHub and Azure (that lands as a separate manual one-off, not a code change); any application code wiring up the resources (each service binding lands with the OpenSpec change that needs it); any Bicep parameters file with real subscription IDs or resource names — only sample values.

## Capabilities

### New Capabilities

- `azure-infrastructure`: the Bicep blueprint for every Azure resource AzureClaw needs, the `azd` project manifest, and the contract that `bicep build` succeeds for every file under `infra/**/*.bicep` on every PR

### Modified Capabilities

- `repository-foundation`: the `Bicep what-if previews on infra PRs` requirement is updated — the workflow no longer treats a missing `infra/main.bicep` as a skip case (the file is now guaranteed to exist after this change merges)

## Impact

- **Affected systems:** local working tree, GitHub Actions (the `ci/bicep-validate` job now actually has files to compile), `bicep-what-if` workflow behavior on PRs touching `infra/`. **No Azure resource is created.**
- **Affected dependencies:** none in `pyproject.toml`. CI installs the Bicep CLI from the Microsoft Bicep release page in the existing `ci/bicep-validate` job; that step already exists and was a no-op until now.
- **Affected APIs:** none (no Python is added or changed in this PR)
- **Affected docs:** the README's "Status" section becomes slightly stale — it still says "no Azure resources have been provisioned," which remains true, but the implication that no Azure infrastructure code exists is no longer accurate. A one-line follow-up doc tweak can land in a separate PR.
- **Reversibility:** fully reversible — revert the PR. Because no resource was created, there is nothing to clean up in any subscription.
