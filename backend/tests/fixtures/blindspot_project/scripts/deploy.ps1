# Deploys the orders API to the staging resource group.
param(
    [string]$ResourceGroup = 'orders-staging',
    [string]$Location = 'westeurope'
)

Write-Host "Deploying to $ResourceGroup in $Location"
New-AzResourceGroupDeployment `
    -ResourceGroupName $ResourceGroup `
    -TemplateFile ../infra/appservice.bicep `
    -location $Location
