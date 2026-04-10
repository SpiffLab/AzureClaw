// ─────────────────────────────────────────────────────────────────────────
// AzureClaw — Container Apps module
//
// Provisions:
//   1. A Container Apps environment wired to the Log Analytics workspace
//      from appinsights.bicep
//   2. The `azureclaw-gateway` Container App with a system-assigned
//      managed identity, an external HTTPS ingress on port 8080, and a
//      placeholder image (mcr.microsoft.com/k8se/quickstart:latest)
//      that the gateway-and-webhooks change will replace.
//
// The gateway Container App's `template.containers` array currently has
// one entry — the gateway itself. A future change (`magentic-research-team`)
// will add a second entry for the browser MCP sidecar that runs
// Playwright in process isolation.
//
// The system-assigned managed identity's principal id is exposed as an
// output so main.bicep can grant it Key Vault Secrets User on the
// Key Vault and AcrPull on the Container Registry.
// ─────────────────────────────────────────────────────────────────────────

@description('Container Apps environment name.')
param environmentName string

@description('Gateway Container App name.')
param gatewayAppName string

@description('Azure region for both resources.')
param location string

@description('Tags applied to every resource.')
param tags object = {}

@description('Log Analytics workspace resource id from appinsights.bicep.')
param logAnalyticsWorkspaceId string

@description('Application Insights connection string for OpenTelemetry export.')
param appInsightsConnectionString string

@description('Placeholder container image. Replaced by the gateway-and-webhooks change once the gateway code exists and CI builds an image.')
param placeholderImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource environment 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    zoneRedundant: false
  }
}

resource gatewayApp 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: gatewayAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      // No registries / secrets configured here yet — the
      // gateway-and-webhooks change wires the ACR pull credential and
      // the Key Vault secret references once a real image exists.
    }
    template: {
      containers: [
        {
          name: 'gateway'
          image: placeholderImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'ENVIRONMENT'
              value: 'dev'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ]
        }
        // Future browser-mcp sidecar slot:
        //
        //   {
        //     name: 'browser-mcp'
        //     image: '<acr-login-server>/azureclaw-browser-mcp:<tag>'
        //     resources: { cpu: json('0.5'), memory: '1Gi' }
        //   }
        //
        // The magentic-research-team OpenSpec change adds it once the
        // browser MCP image is built and pushed to ACR.
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

output environmentId string = environment.id
output environmentName string = environment.name
output gatewayAppName string = gatewayApp.name
output gatewayPrincipalId string = gatewayApp.identity.principalId
output gatewayFqdn string = gatewayApp.properties.configuration.ingress.fqdn
