// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Azure AI Foundry module
//
// Provisions an Azure AI Foundry account (Microsoft.CognitiveServices
// kind 'AIServices') with TWO model deployments:
//
//   1. gpt-5.4-mini             — chat completions, default for every
//                                  ChatAgent in the workflow (Triage,
//                                  Chat, Magentic team, …)
//   2. text-embedding-3-large   — 3072-dim embeddings, used by the
//                                  AISearchContextProvider for semantic
//                                  recall. The vector dimensions in
//                                  aisearch.bicep MUST match this model.
//
// Both deployments live in the same module so the embedding-dimension
// contract between Foundry and AI Search is reviewable in a single PR.
//
// Local-auth is disabled — accessors authenticate via Entra ID.
// ─────────────────────────────────────────────────────────────────────────

@description('Foundry account name.')
param accountName string

@description('Azure region for the Foundry account. Use a region with broad model availability (eastus2, swedencentral, etc.).')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('Capacity (TPM in thousands) for the chat model deployment.')
param chatCapacity int = 10

@description('Capacity (TPM in thousands) for the embedding model deployment.')
param embeddingCapacity int = 30

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundry
  name: 'gpt-5.4-mini'
  sku: {
    name: 'Standard'
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5.4-mini'
      version: '2026-01-01'
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundry
  name: 'text-embedding-3-large'
  sku: {
    name: 'Standard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [
    chatDeployment // Foundry only allows one deployment operation in flight at a time
  ]
}

output accountId string = foundry.id
output accountName string = foundry.name
output endpoint string = foundry.properties.endpoint
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
