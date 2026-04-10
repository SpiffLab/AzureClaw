// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Cosmos DB module
//
// Provisions an Azure Cosmos DB (NoSQL API) account with the four
// containers AzureClaw needs:
//
//   - threads      → AgentThread persistence,        partition: /session_id
//   - checkpoints  → WorkflowRunState checkpointing, partition: /session_id
//   - audit        → cross-boundary audit log,       partition: /session_id
//   - sites        → registered on-prem connectors,  partition: /site_id
//
// Local-auth is disabled — every accessor authenticates via Entra ID
// (DefaultAzureCredential) and the data-plane RBAC role is granted
// separately by main.bicep to the Container Apps gateway managed
// identity.
// ─────────────────────────────────────────────────────────────────────────

@description('Cosmos DB account name (must be globally unique, 3-44 chars, lowercase letters, numbers, hyphens).')
param accountName string

@description('Azure region for the Cosmos DB account.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('Maximum autoscale RU/s for each container. 1000 RU/s minimum on autoscale.')
@minValue(1000)
param maxAutoscaleThroughput int = 1000

var databaseName = 'azureclaw'

resource account 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: []
    disableLocalAuth: true
    minimalTlsVersion: 'Tls12'
    publicNetworkAccess: 'Enabled'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: account
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

var sessionContainers = [
  'threads'
  'checkpoints'
  'audit'
]

resource sessionScopedContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = [
  for name in sessionContainers: {
    parent: database
    name: name
    properties: {
      resource: {
        id: name
        partitionKey: {
          paths: [
            '/session_id'
          ]
          kind: 'Hash'
        }
        indexingPolicy: {
          indexingMode: 'consistent'
          automatic: true
          includedPaths: [
            {
              path: '/*'
            }
          ]
          excludedPaths: [
            {
              path: '/"_etag"/?'
            }
          ]
        }
      }
      options: {
        autoscaleSettings: {
          maxThroughput: maxAutoscaleThroughput
        }
      }
    }
  }
]

resource sitesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: 'sites'
  properties: {
    resource: {
      id: 'sites'
      partitionKey: {
        paths: [
          '/site_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
    }
    options: {
      autoscaleSettings: {
        maxThroughput: maxAutoscaleThroughput
      }
    }
  }
}

output accountId string = account.id
output accountName string = account.name
output endpoint string = account.properties.documentEndpoint
output databaseName string = database.name
