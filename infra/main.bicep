// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — main entrypoint
//
// Subscription-scoped Bicep that creates the resource group and invokes
// every per-service module to provision AzureClaw's complete Azure
// footprint:
//
//   - Cosmos DB                  (cosmos.bicep)
//   - Azure AI Search            (aisearch.bicep)
//   - Key Vault                  (keyvault.bicep)
//   - Application Insights       (appinsights.bicep)
//   - Service Bus                (servicebus.bicep)
//   - Blob Storage               (storage.bicep)
//   - Container Apps             (containerapps.bicep)
//   - Azure Container Registry   (acr.bicep)
//   - Azure AI Content Safety    (contentsafety.bicep)
//   - Azure AI Foundry           (foundry.bicep)
//
// IMPORTANT: this file is *runnable* but is NOT run by this PR. Deploy
// is gated to the `first-deploy-dev` OpenSpec change (#23) behind a
// manual workflow_dispatch and a required reviewer on the dev-deploy
// environment.
// ─────────────────────────────────────────────────────────────────────────

targetScope = 'subscription'

// ──────────────────────────────────────────────────────────────────────
// Parameters
// ──────────────────────────────────────────────────────────────────────

@description('Resource name prefix. Used in resource group name and unique resource names.')
param prefix string = 'azureclaw'

@description('Deployment environment. Affects resource group name and capacity defaults.')
@allowed([
  'dev'
  'prod'
])
param environment string = 'dev'

@description('Azure region for the resource group and every resource inside it.')
param location string = deployment().location

@description('Object id of an Entra ID principal that should receive Key Vault Secrets User during early bring-up. Typically the operator running azd up.')
param operatorPrincipalId string = ''

@description('Common tags applied to every resource.')
param tags object = {
  project: 'azureclaw'
  environment: environment
  managedBy: 'bicep'
}

// ──────────────────────────────────────────────────────────────────────
// Naming
// ──────────────────────────────────────────────────────────────────────

var resourceGroupName = '${prefix}-${environment}-rg'

// `uniqueString` derives a 13-char hash from the inputs. We use it to
// disambiguate globally-unique resource names without exposing the raw
// subscription id.
var uniqueSuffix = uniqueString(subscription().id, prefix, environment)

var cosmosAccountName = toLower('${prefix}-${environment}-cdb-${uniqueSuffix}')
var searchServiceName = toLower('${prefix}-${environment}-srch-${uniqueSuffix}')
var keyVaultName = toLower('${prefix}-${environment}-kv-${uniqueSuffix}')
var logAnalyticsWorkspaceName = '${prefix}-${environment}-log'
var appInsightsName = '${prefix}-${environment}-ai'
var serviceBusNamespaceName = toLower('${prefix}-${environment}-sb-${uniqueSuffix}')
var storageAccountName = toLower(replace('${prefix}${environment}st${uniqueSuffix}', '-', ''))
var acaEnvironmentName = '${prefix}-${environment}-aca-env'
var gatewayAppName = '${prefix}-${environment}-gateway'
var registryName = toLower(replace('${prefix}${environment}acr${uniqueSuffix}', '-', ''))
var contentSafetyAccountName = toLower('${prefix}-${environment}-cs-${uniqueSuffix}')
var foundryAccountName = toLower('${prefix}-${environment}-foundry-${uniqueSuffix}')

// ──────────────────────────────────────────────────────────────────────
// Resource group
// ──────────────────────────────────────────────────────────────────────

resource rg 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ──────────────────────────────────────────────────────────────────────
// Stage 1: resources with no internal dependencies
// ──────────────────────────────────────────────────────────────────────

module cosmos 'modules/cosmos.bicep' = {
  scope: rg
  name: 'cosmos-deploy'
  params: {
    accountName: cosmosAccountName
    location: location
    tags: tags
  }
}

module aisearch 'modules/aisearch.bicep' = {
  scope: rg
  name: 'aisearch-deploy'
  params: {
    serviceName: searchServiceName
    location: location
    tags: tags
  }
}

module appInsightsModule 'modules/appinsights.bicep' = {
  scope: rg
  name: 'appinsights-deploy'
  params: {
    workspaceName: logAnalyticsWorkspaceName
    appInsightsName: appInsightsName
    location: location
    tags: tags
  }
}

module servicebus 'modules/servicebus.bicep' = {
  scope: rg
  name: 'servicebus-deploy'
  params: {
    namespaceName: serviceBusNamespaceName
    location: location
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage-deploy'
  params: {
    storageAccountName: storageAccountName
    location: location
    tags: tags
  }
}

module contentsafety 'modules/contentsafety.bicep' = {
  scope: rg
  name: 'contentsafety-deploy'
  params: {
    accountName: contentSafetyAccountName
    location: location
    tags: tags
  }
}

module foundry 'modules/foundry.bicep' = {
  scope: rg
  name: 'foundry-deploy'
  params: {
    accountName: foundryAccountName
    location: location
    tags: tags
  }
}

// ──────────────────────────────────────────────────────────────────────
// Stage 2: Container Apps environment + gateway (depends on Log Analytics)
// ──────────────────────────────────────────────────────────────────────

module containerapps 'modules/containerapps.bicep' = {
  scope: rg
  name: 'containerapps-deploy'
  params: {
    environmentName: acaEnvironmentName
    gatewayAppName: gatewayAppName
    location: location
    tags: tags
    logAnalyticsWorkspaceId: appInsightsModule.outputs.workspaceId
    appInsightsConnectionString: appInsightsModule.outputs.connectionString
  }
}

// ──────────────────────────────────────────────────────────────────────
// Stage 3: ACR + Key Vault (depend on the gateway managed identity)
// ──────────────────────────────────────────────────────────────────────

module acr 'modules/acr.bicep' = {
  scope: rg
  name: 'acr-deploy'
  params: {
    registryName: registryName
    location: location
    tags: tags
    principalId: containerapps.outputs.gatewayPrincipalId
  }
}

// During early bring-up the operator's Entra principal also gets
// Key Vault Secrets User so they can manually `az keyvault secret set`
// the channel tokens. The gateway always gets it via its managed
// identity. We pick whichever principalId is non-empty.
var keyVaultPrincipalId = empty(operatorPrincipalId) ? containerapps.outputs.gatewayPrincipalId : operatorPrincipalId

module keyvault 'modules/keyvault.bicep' = {
  scope: rg
  name: 'keyvault-deploy'
  params: {
    vaultName: keyVaultName
    location: location
    tags: tags
    principalId: keyVaultPrincipalId
    enablePurgeProtection: environment == 'prod'
  }
}

// If the operator principal id is set AND the gateway principal id is
// different, grant the gateway too. Bicep does not allow conditional
// modules to share names so we declare a second keyvault module
// instance only when needed.
module keyvaultGatewayGrant 'modules/keyvault.bicep' = if (!empty(operatorPrincipalId)) {
  scope: rg
  name: 'keyvault-gateway-grant'
  params: {
    vaultName: keyVaultName
    location: location
    tags: tags
    principalId: containerapps.outputs.gatewayPrincipalId
    enablePurgeProtection: environment == 'prod'
  }
  dependsOn: [
    keyvault
  ]
}

// ──────────────────────────────────────────────────────────────────────
// Outputs — consumed by `azd` and by application code at startup
// ──────────────────────────────────────────────────────────────────────

output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_LOCATION string = location

output AZURE_COSMOS_ENDPOINT string = cosmos.outputs.endpoint
output AZURE_COSMOS_DATABASE string = cosmos.outputs.databaseName

output AZURE_SEARCH_ENDPOINT string = aisearch.outputs.endpoint
output AZURE_SEARCH_INDEX string = aisearch.outputs.indexName

output AZURE_KEY_VAULT_URI string = keyvault.outputs.vaultUri

output AZURE_APP_INSIGHTS_CONNECTION_STRING string = appInsightsModule.outputs.connectionString

output AZURE_SERVICE_BUS_NAMESPACE string = servicebus.outputs.namespaceName
output AZURE_SERVICE_BUS_QUEUE string = servicebus.outputs.queueName

output AZURE_STORAGE_BLOB_ENDPOINT string = storage.outputs.blobEndpoint
output AZURE_STORAGE_CANVAS_CONTAINER string = storage.outputs.canvasContainerName

output AZURE_CONTAINER_APPS_ENVIRONMENT string = containerapps.outputs.environmentName
output AZURE_CONTAINER_APPS_GATEWAY string = containerapps.outputs.gatewayAppName
output AZURE_CONTAINER_APPS_GATEWAY_FQDN string = containerapps.outputs.gatewayFqdn

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.outputs.loginServer

output AZURE_CONTENT_SAFETY_ENDPOINT string = contentsafety.outputs.endpoint

output AZURE_FOUNDRY_ENDPOINT string = foundry.outputs.endpoint
output AZURE_FOUNDRY_CHAT_DEPLOYMENT string = foundry.outputs.chatDeploymentName
output AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT string = foundry.outputs.embeddingDeploymentName
