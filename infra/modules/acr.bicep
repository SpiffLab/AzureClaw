// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Azure Container Registry module
//
// Provisions an ACR at Basic SKU (sufficient for one gateway image and
// the future browser MCP sidecar image) and grants the Container Apps
// gateway managed identity the built-in `AcrPull` role at the registry
// scope. Admin user is disabled — the gateway authenticates via its
// managed identity, never via username/password.
// ─────────────────────────────────────────────────────────────────────────

@description('ACR registry name (must be globally unique, 5-50 alphanumeric chars).')
param registryName string

@description('Azure region for the registry.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('Object id of the principal that should receive AcrPull. Typically the gateway Container App managed identity.')
param principalId string

resource registry 'Microsoft.ContainerRegistry/registries@2024-11-01-preview' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    anonymousPullEnabled: false
  }
}

// Built-in role: AcrPull
// https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#acrpull
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, principalId, acrPullRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      acrPullRoleId
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output registryId string = registry.id
output registryName string = registry.name
output loginServer string = registry.properties.loginServer
