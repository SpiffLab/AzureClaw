// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Service Bus module
//
// Provisions a Service Bus namespace and the `approvals` queue used by
// the human-in-the-loop approval flow. When a tool marked
// require_approval=True fires, the workflow checkpoints and emits a
// FunctionApprovalRequestContent which is published to this queue.
// The channel adapters consume the queue and render the approval
// prompt in their native UI (Adaptive Card / Block Kit / Discord
// components / interactive WhatsApp buttons).
//
// Local-auth is disabled — every accessor authenticates via Entra ID.
// Standard SKU is required for queue features (sessions, dead-lettering,
// duplicate detection).
// ─────────────────────────────────────────────────────────────────────────

@description('Service Bus namespace name (must be globally unique, 6-50 chars, lowercase letters, numbers, hyphens).')
param namespaceName string

@description('Azure region for the Service Bus namespace.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

resource namespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource approvalsQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: namespace
  name: 'approvals'
  properties: {
    lockDuration: 'PT5M'
    maxSizeInMegabytes: 1024
    requiresDuplicateDetection: false
    requiresSession: false
    defaultMessageTimeToLive: 'P14D'
    deadLetteringOnMessageExpiration: true
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    maxDeliveryCount: 10
    enablePartitioning: false
    enableExpress: false
  }
}

output namespaceId string = namespace.id
output namespaceName string = namespace.name
output queueName string = approvalsQueue.name
