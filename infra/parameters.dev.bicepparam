// AzureClaw — dev environment Bicep parameters.
//
// This file uses placeholder values for the dev environment. The
// operator overrides them at `azd up` time via environment variables:
//
//   AZURE_ENV_NAME      → environment
//   AZURE_LOCATION      → location
//   AZURE_PRINCIPAL_ID  → operatorPrincipalId
//
// Real subscription ids and tenant ids are NOT committed here. They
// live in the GitHub repository variables consumed by .github/workflows/
// release.yml and .github/workflows/bicep-what-if.yml.
//
// IMPORTANT: this file is NOT used by any deploy in this PR. The
// `first-deploy-dev` OpenSpec change (#23) is the first one that
// references it.

using './main.bicep'

param prefix = 'azureclaw'
param environment = 'dev'
param location = 'eastus2'
param operatorPrincipalId = ''
