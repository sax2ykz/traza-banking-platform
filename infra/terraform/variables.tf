variable "subscription_id" {
  description = "Azure subscription used by BancoCloud."
  type        = string
}

variable "resource_group_name" {
  description = "Existing BancoCloud resource group."
  type        = string
  default     = "rg-bancocloud-dev"
}

variable "location" {
  description = "Azure region used by the existing BancoCloud resource group."
  type        = string
  default     = "westus"
}

variable "foundry_account_name" {
  description = "Existing Microsoft Foundry / AIServices account."
  type        = string
  default     = "ai-bancocloud-genai-a7x9"
}
