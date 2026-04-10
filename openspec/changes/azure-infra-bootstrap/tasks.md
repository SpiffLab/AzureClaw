## 1. azd project manifest

- [ ] 1.1 Create `azure.yaml` at the repo root with `name: azureclaw`, `metadata.template: azureclaw@0.1.0`, `infra.path: infra`, `infra.module: main`, and one service entry `gateway` with `language: python` / `host: containerapp` / `project: ./src/azureclaw`
- [ ] 1.2 Verify `azure.yaml` parses against the `azd` schema (manual check; `azd config get` if azd is installed locally)

## 2. Subscription-scoped main.bicep

- [ ] 2.1 Create `infra/main.bicep` with `targetScope = 'subscription'`
- [ ] 2.2 Declare parameters: `prefix` (default `'azureclaw'`), `environment` (allowed values `'dev'`, `'prod'`), `location` (default `deployment().location`), and `principalId` (operator's Entra OID for manual access during early bring-up)
- [ ] 2.3 Declare variables for unique resource naming using `uniqueString(subscription().id, prefix, environment)`
- [ ] 2.4 Create the resource group `${prefix}-${environment}-rg`
- [ ] 2.5 Invoke every per-service module (cosmos, aisearch, keyvault, appinsights, servicebus, storage, containerapps, acr, contentsafety, foundry) with `scope: rg`
- [ ] 2.6 Pass cross-module dependencies via outputs (e.g., the Container Apps environment's principal id flows into `keyvault.bicep`)
- [ ] 2.7 Declare top-level outputs for the values `azd` and the application code need (resource group name, ACR login server, Cosmos endpoint, AI Search endpoint, Foundry endpoint, Container Apps env id, Key Vault uri, App Insights connection string)

## 3. Bicep parameters file

- [ ] 3.1 Create `infra/parameters.dev.bicepparam` using the `using './main.bicep'` syntax with sample values for `prefix`, `environment = 'dev'`, `location = 'eastus2'`, and a placeholder `principalId`
- [ ] 3.2 Add a comment block at the top of the file explaining how to override values via env vars at `azd up` time

## 4. Per-service Bicep modules

### 4.1 Cosmos DB

- [ ] 4.1.1 Create `infra/modules/cosmos.bicep`
- [ ] 4.1.2 Declare a Cosmos DB account with `kind: 'GlobalDocumentDB'`, autoscale enabled at 1000 RU/s, and `disableLocalAuth: true` (managed-identity-only access)
- [ ] 4.1.3 Create the `azureclaw` SQL database
- [ ] 4.1.4 Create the four containers `threads`, `checkpoints`, `audit` (all partitioned on `/session_id`), and `sites` (partitioned on `/site_id`)
- [ ] 4.1.5 Output `accountId`, `accountName`, `endpoint`, and `databaseName`

### 4.2 Azure AI Search

- [ ] 4.2.1 Create `infra/modules/aisearch.bicep`
- [ ] 4.2.2 Declare an Azure AI Search service at the `basic` SKU with system-assigned managed identity and `disableLocalAuth: true`
- [ ] 4.2.3 Create the `azureclaw-memory` index with fields: `id` (Edm.String, key, retrievable), `session_id` (Edm.String, filterable, retrievable), `text` (Edm.String, searchable, retrievable), `embedding` (Collection(Edm.Single), dimensions 3072, vectorSearchProfile), `created_at` (Edm.DateTimeOffset, filterable, sortable)
- [ ] 4.2.4 Configure a vector search profile + algorithm (HNSW) for the `embedding` field
- [ ] 4.2.5 Output `serviceId`, `serviceName`, `endpoint`, and `indexName`

### 4.3 Key Vault

- [ ] 4.3.1 Create `infra/modules/keyvault.bicep`
- [ ] 4.3.2 Accept `principalId` parameter
- [ ] 4.3.3 Declare a Key Vault with RBAC authorization (not access policies — RBAC is the modern path) and soft-delete enabled
- [ ] 4.3.4 Assign the `Key Vault Secrets User` built-in role to the `principalId` at the Key Vault scope
- [ ] 4.3.5 Output `vaultId`, `vaultName`, and `vaultUri`

### 4.4 Application Insights + Log Analytics

- [ ] 4.4.1 Create `infra/modules/appinsights.bicep`
- [ ] 4.4.2 Declare a Log Analytics workspace
- [ ] 4.4.3 Declare an Application Insights component linked to the Log Analytics workspace via `WorkspaceResourceId`
- [ ] 4.4.4 Output `workspaceId`, `appInsightsId`, `appInsightsName`, and `connectionString` (the latter is needed by `azure-monitor-opentelemetry`)

### 4.5 Service Bus

- [ ] 4.5.1 Create `infra/modules/servicebus.bicep`
- [ ] 4.5.2 Declare a Service Bus namespace at the `Standard` SKU with `disableLocalAuth: true`
- [ ] 4.5.3 Create the `approvals` queue with reasonable defaults (lockDuration 5 min, max delivery 10, dead-lettering enabled)
- [ ] 4.5.4 Output `namespaceId`, `namespaceName`, and `queueName`

### 4.6 Storage

- [ ] 4.6.1 Create `infra/modules/storage.bicep`
- [ ] 4.6.2 Declare a Storage account at `Standard_LRS`, with `allowSharedKeyAccess: false` and `minimumTlsVersion: 'TLS1_2'`
- [ ] 4.6.3 Create a `canvas` blob container
- [ ] 4.6.4 Output `storageAccountId`, `storageAccountName`, `blobEndpoint`, and `canvasContainerName`

### 4.7 Container Apps

- [ ] 4.7.1 Create `infra/modules/containerapps.bicep`
- [ ] 4.7.2 Accept `logAnalyticsWorkspaceId` parameter from `appinsights.bicep`
- [ ] 4.7.3 Declare a Container Apps environment wired to the Log Analytics workspace
- [ ] 4.7.4 Declare the `azureclaw-gateway` Container App with `identity: { type: 'SystemAssigned' }`, ingress on port 8080, and the placeholder image `mcr.microsoft.com/k8se/quickstart:latest`
- [ ] 4.7.5 Add a comment in `template.containers` documenting the future browser MCP sidecar slot
- [ ] 4.7.6 Output `environmentId`, `environmentName`, `gatewayAppName`, `gatewayPrincipalId`, and `gatewayFqdn`

### 4.8 Azure Container Registry

- [ ] 4.8.1 Create `infra/modules/acr.bicep`
- [ ] 4.8.2 Accept `principalId` parameter (the gateway Container App's managed identity)
- [ ] 4.8.3 Declare an ACR at `Basic` SKU with `adminUserEnabled: false`
- [ ] 4.8.4 Assign the `AcrPull` built-in role to `principalId` at the registry scope
- [ ] 4.8.5 Output `registryId`, `registryName`, and `loginServer`

### 4.9 Azure AI Content Safety

- [ ] 4.9.1 Create `infra/modules/contentsafety.bicep`
- [ ] 4.9.2 Declare a Cognitive Services account with `kind: 'ContentSafety'` at `S0` SKU and `disableLocalAuth: true`
- [ ] 4.9.3 Output `accountId`, `accountName`, and `endpoint`

### 4.10 Azure AI Foundry

- [ ] 4.10.1 Create `infra/modules/foundry.bicep`
- [ ] 4.10.2 Declare an Azure AI Foundry account (`Microsoft.CognitiveServices/accounts` with `kind: 'AIServices'`) at `S0` SKU with system-assigned managed identity and `disableLocalAuth: true`
- [ ] 4.10.3 Create a chat-completions deployment named `gpt-5.4-mini` referencing the model `gpt-5.4-mini` at `Standard` SKU
- [ ] 4.10.4 Create an embeddings deployment named `text-embedding-3-large` referencing the model of the same name
- [ ] 4.10.5 Output `accountId`, `accountName`, `endpoint`, `chatDeploymentName`, and `embeddingDeploymentName`

## 5. CI workflow updates

- [ ] 5.1 In `.github/workflows/bicep-what-if.yml`, remove the "skip if `infra/main.bicep` does not exist" branch from the `what-if` job (the file now always exists)
- [ ] 5.2 Verify the `noop` job (active when `AZURE_DEV_SUBSCRIPTION_ID` is empty) still works as the external-contributor escape hatch
- [ ] 5.3 Confirm `.github/workflows/ci.yml`'s `ci/bicep-validate` job still iterates over `infra/**/*.bicep` (no change needed; the existing loop already handles new files)
- [ ] 5.4 Confirm `.github/workflows/release.yml`'s guard step still references `infra/main.bicep` (no change needed; the file now exists so the guard passes)

## 6. Verification

- [ ] 6.1 Install the Bicep CLI locally (`az bicep install` or download a binary)
- [ ] 6.2 Run `bicep build infra/main.bicep --stdout > /dev/null` and confirm exit 0
- [ ] 6.3 Run `bicep build` against every file under `infra/modules/` and confirm all succeed
- [ ] 6.4 Run `npx -y @fission-ai/openspec validate azure-infra-bootstrap` and confirm clean
- [ ] 6.5 Confirm `pytest -m local` still passes (no Python regressions; this change should not touch any Python file)
- [ ] 6.6 Confirm `ruff check src tests`, `ruff format --check src tests`, and `pyright src tests` all still pass

## 7. Commit and PR

- [ ] 7.1 Commit (1) — OpenSpec artifacts only — `spec: azure-infra-bootstrap — Bicep blueprint + azd manifest, no deploy`
- [ ] 7.2 Commit (2) — implementation — `feat: azure-infra-bootstrap implementation`
- [ ] 7.3 Push `feature/azure-infra-bootstrap` to origin
- [ ] 7.4 Open PR against `develop` via `gh pr create` with the full template body
