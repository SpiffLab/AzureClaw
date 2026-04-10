// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Azure AI Content Safety module
//
// Provisions an Azure AI Content Safety resource (Cognitive Services
// account with kind 'ContentSafety'). The safety middleware in
// `src/azureclaw/middleware/safety.py` will call its endpoint via
// `azureclaw.azure.credential.build_credential` once that change lands.
//
// Local-auth is disabled — accessors authenticate via Entra ID.
// ─────────────────────────────────────────────────────────────────────────

@description('Content Safety account name.')
param accountName string

@description('Azure region for the account.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'ContentSafety'
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

output accountId string = contentSafety.id
output accountName string = contentSafety.name
output endpoint string = contentSafety.properties.endpoint
