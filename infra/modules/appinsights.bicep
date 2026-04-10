// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Application Insights + Log Analytics module
//
// Provisions a Log Analytics workspace and an Application Insights
// component linked to it via WorkspaceResourceId. AzureClaw's
// observability stack uses `azure-monitor-opentelemetry` to export
// MAF-emitted OTel spans here, so the connection string output by this
// module flows into Key Vault as `app-insights-connection-string` and
// is resolved at gateway startup.
// ─────────────────────────────────────────────────────────────────────────

@description('Log Analytics workspace name.')
param workspaceName string

@description('Application Insights component name.')
param appInsightsName string

@description('Azure region for both resources.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('Number of days to retain Log Analytics data.')
@minValue(30)
@maxValue(730)
param retentionInDays int = 30

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output workspaceId string = workspace.id
output workspaceName string = workspace.name
output appInsightsId string = appInsights.id
output appInsightsName string = appInsights.name
output connectionString string = appInsights.properties.ConnectionString
