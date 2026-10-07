resource "azurerm_resource_group" "bancocloud" {
  name     = var.resource_group_name
  location = var.location

  lifecycle {
    prevent_destroy = true
  }
}

data "azurerm_resources" "foundry_account" {
  name                = var.foundry_account_name
  resource_group_name = azurerm_resource_group.bancocloud.name
  type                = "Microsoft.CognitiveServices/accounts"
}

data "azurerm_resources" "foundry_project" {
  resource_group_name = azurerm_resource_group.bancocloud.name
  type                = "Microsoft.CognitiveServices/accounts/projects"
}
