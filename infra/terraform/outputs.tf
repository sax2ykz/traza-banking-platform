output "resource_group_id" {
  description = "Managed BancoCloud Resource Group ID."
  value       = azurerm_resource_group.bancocloud.id
}

output "resource_group_location" {
  description = "BancoCloud Resource Group location."
  value       = azurerm_resource_group.bancocloud.location
}

output "foundry_account_resources" {
  description = "Existing Foundry account resources discovered in Azure."
  value = [
    for item in data.azurerm_resources.foundry_account.resources : {
      name     = item.name
      id       = item.id
      type     = item.type
      location = item.location
    }
  ]
}

output "foundry_project_resources" {
  description = "Existing Foundry project resources discovered in Azure."
  value = [
    for item in data.azurerm_resources.foundry_project.resources : {
      name     = item.name
      id       = item.id
      type     = item.type
      location = item.location
    }
  ]
}
