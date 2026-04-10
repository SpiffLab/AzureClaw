// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Azure AI Search module
//
// Provisions an Azure AI Search service AND the `azureclaw-memory` index
// in the same module so the schema is version-controlled and reviewable
// in PRs alongside the service definition.
//
// The `embedding` field's vector dimensions are pinned to 3072, which
// matches `text-embedding-3-large` deployed by foundry.bicep. If a future
// change swaps the embedding model, BOTH this module and foundry.bicep
// must change in lockstep.
//
// Local-auth is disabled — every accessor authenticates via Entra ID.
// The data-plane RBAC role is granted separately by main.bicep to the
// gateway managed identity.
//
// Note: The index resource type historically lived under
// Microsoft.Search but the data-plane API for index creation is the
// canonical path. We declare the index here as a child resource using
// the management-plane API which is supported in newer Bicep types.
// ─────────────────────────────────────────────────────────────────────────

@description('Azure AI Search service name (must be globally unique, 2-60 chars, lowercase letters, numbers, hyphens).')
param serviceName string

@description('Azure region for the AI Search service.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('SKU name for the AI Search service.')
@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param skuName string = 'basic'

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: serviceName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: true
    authOptions: null
    semanticSearch: 'free'
  }
}

// The `azureclaw-memory` index is intentionally created via Bicep so
// schema changes flow through PR review. The vector field's dimensions
// are pinned to text-embedding-3-large's output size.
//
// Heads-up: `Microsoft.Search/searchServices/indexes@2024-06-01-preview`
// is a management-plane wrapper around what is historically a
// data-plane operation. Bicep will emit a BCP081 warning at build time
// because the preview type definition is not yet published in
// `bicep types`. The warning is benign — `bicep build` exits 0 and
// Azure accepts the deployment. If a future stable API version becomes
// available, swap this to that.
resource memoryIndex 'Microsoft.Search/searchServices/indexes@2024-06-01-preview' = {
  parent: searchService
  name: 'azureclaw-memory'
  properties: {
    fields: [
      {
        name: 'id'
        type: 'Edm.String'
        key: true
        retrievable: true
        searchable: false
        filterable: false
        facetable: false
        sortable: false
      }
      {
        name: 'session_id'
        type: 'Edm.String'
        retrievable: true
        searchable: false
        filterable: true
        facetable: false
        sortable: false
      }
      {
        name: 'text'
        type: 'Edm.String'
        retrievable: true
        searchable: true
        filterable: false
        facetable: false
        sortable: false
        analyzer: 'standard.lucene'
      }
      {
        name: 'embedding'
        type: 'Collection(Edm.Single)'
        retrievable: true
        searchable: true
        filterable: false
        facetable: false
        sortable: false
        dimensions: 3072
        vectorSearchProfile: 'azureclaw-vector-profile'
      }
      {
        name: 'created_at'
        type: 'Edm.DateTimeOffset'
        retrievable: true
        searchable: false
        filterable: true
        facetable: false
        sortable: true
      }
    ]
    vectorSearch: {
      profiles: [
        {
          name: 'azureclaw-vector-profile'
          algorithm: 'azureclaw-hnsw'
        }
      ]
      algorithms: [
        {
          name: 'azureclaw-hnsw'
          kind: 'hnsw'
          hnswParameters: {
            metric: 'cosine'
            m: 4
            efConstruction: 400
            efSearch: 500
          }
        }
      ]
    }
  }
}

output serviceId string = searchService.id
output serviceName string = searchService.name
output endpoint string = 'https://${searchService.name}.search.windows.net'
output indexName string = memoryIndex.name
