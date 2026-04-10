// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Key Vault module
//
// Provisions a Key Vault using the modern RBAC authorization model
// (NOT the legacy access policies model). The Container Apps gateway
// managed identity is granted the built-in `Key Vault Secrets User`
// role, which allows GET and LIST on secrets — exactly what AzureClaw
// needs to resolve `@kv:` config pointers at startup.
//
// Soft delete is enabled (it is also the Azure default and cannot be
// turned off in any new vault). Purge protection is intentionally NOT
// enabled here so the dev resource group can be torn down cleanly
// during early bring-up; prod parameters should override this.
// ─────────────────────────────────────────────────────────────────────────

@description('Key Vault name (must be globally unique, 3-24 chars).')
param vaultName string

@description('Azure region for the Key Vault.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('Object id of the principal that should receive Key Vault Secrets User. Typically the gateway Container App managed identity.')
param principalId string

@description('Enable purge protection. Recommended for prod.')
param enablePurgeProtection bool = false

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: vaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: enablePurgeProtection ? true : null
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Built-in role: Key Vault Secrets User
// https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#key-vault-secrets-user
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource secretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: vault
  name: guid(vault.id, principalId, keyVaultSecretsUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      keyVaultSecretsUserRoleId
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output vaultId string = vault.id
output vaultName string = vault.name
output vaultUri string = vault.properties.vaultUri
