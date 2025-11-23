resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

# Resource Groups
resource "azurerm_resource_group" "aks_dev" {
  name     = var.aks_dev_rg_name
  location = var.location
  tags     = var.tags
}
resource "azurerm_resource_group" "aks_prod" {
  name     = var.aks_prod_rg_name
  location = var.location
  tags     = var.tags
}
resource "azurerm_resource_group" "platform" {
  name     = var.platform_rg_name
  location = var.location
  tags     = var.tags
}

# ACR
resource "azurerm_container_registry" "acr" {
  name                = "${var.acr_name_prefix}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.platform.name
  location            = var.location
  sku                 = "Standard"
  admin_enabled       = false
  tags                = var.tags
}

# Storage Account + containers
resource "azurerm_storage_account" "storage" {
  name                     = "${var.storage_account_name_prefix}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.platform.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = var.tags
}
resource "azurerm_storage_container" "artifacts_dev" {
  name                  = "dosm-artifacts-dev"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}
resource "azurerm_storage_container" "artifacts_prod" {
  name                  = "dosm-artifacts-prod"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

# Key Vault
resource "azurerm_key_vault" "kv" {
  name                        = var.key_vault_name
  location                    = var.location
  resource_group_name         = azurerm_resource_group.platform.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  purge_protection_enabled    = true
  soft_delete_retention_days  = 7
  enable_rbac_authorization   = true
  public_network_access_enabled = true
  tags                        = var.tags
}

data "azurerm_client_config" "current" {}

# PostgreSQL Flexible Server + Databases
resource "azurerm_postgresql_flexible_server" "pg" {
  name                   = var.postgres_server_name
  resource_group_name    = azurerm_resource_group.platform.name
  location               = var.location
  administrator_login    = var.postgres_admin_user
  administrator_password = var.postgres_admin_password
  sku_name               = "B_Standard_B1ms"
  storage_mb             = var.postgres_storage_mb
  version                = var.postgres_version
  backup_retention_days  = 7
  public_network_access_enabled = true
  tags = var.tags
  lifecycle { ignore_changes = [zone] }
}

resource "azurerm_postgresql_flexible_server_database" "devdb" {
  name      = var.db_dev_name
  server_id = azurerm_postgresql_flexible_server.pg.id
}
resource "azurerm_postgresql_flexible_server_database" "proddb" {
  name      = var.db_prod_name
  server_id = azurerm_postgresql_flexible_server.pg.id
}

# Firewall rule allow Azure services (0.0.0.0)
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "allow-azure"
  server_id        = azurerm_postgresql_flexible_server.pg.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

## AKS Clusters (Dev & Prod) cost-optimized dev, scalable prod
resource "azurerm_kubernetes_cluster" "aks_dev" {
  name                = var.aks_dev_name
  location            = var.location
  resource_group_name = azurerm_resource_group.aks_dev.name
  dns_prefix          = "${var.aks_dev_name}-dns"

  kubernetes_version = "1.32.9"

  default_node_pool {
    name                 = "system"
    vm_size              = var.aks_dev_node_size
    enable_auto_scaling  = true
    min_count            = var.aks_dev_min_count
    max_count            = var.aks_dev_max_count
    type                 = "VirtualMachineScaleSets"
    orchestrator_version = "1.32.9"
    temporary_name_for_rotation = "systemtmp"
  }

  identity {
    type = "SystemAssigned"
  }
  role_based_access_control_enabled = true
  # Monitoring addon omitted for simplicity; add oms_agent block if Log Analytics is required.
  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    outbound_type     = "loadBalancer"
  }
  tags = var.tags
}

resource "azurerm_kubernetes_cluster" "aks_prod" {
  name                = var.aks_prod_name
  location            = var.location
  resource_group_name = azurerm_resource_group.aks_prod.name
  dns_prefix          = "${var.aks_prod_name}-dns"

  kubernetes_version = "1.32.9"

  default_node_pool {
    name                 = "system"
    vm_size              = var.aks_prod_node_size
    enable_auto_scaling  = true
    min_count            = var.aks_prod_min_count
    max_count            = var.aks_prod_max_count
    type                 = "VirtualMachineScaleSets"
    orchestrator_version = "1.32.9"
    temporary_name_for_rotation = "systemtmp"
  }

  identity {
    type = "SystemAssigned"
  }
  role_based_access_control_enabled = true
  # Monitoring addon omitted for simplicity; add oms_agent block if Log Analytics is required.
  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    outbound_type     = "loadBalancer"
  }
  tags = var.tags
}

## ACR role assignments removed temporarily due to insufficient permissions.
## Re-add once principal has 'Owner' or appropriate rights to assign roles.

# Key Vault Secrets (do not commit real values; pass via tfvars)
## Key Vault secrets omitted until RBAC roles (Secrets Officer/Administrator) are granted.
## Reintroducing ACR & Key Vault secret resources now that roles are granted
## Role assignments & secrets removed again due to persistent 403 RBAC propagation delay.
## Will reapply once Owner/User Access Admin and KV RBAC have propagated (allow ~30+ mins).

resource "kubernetes_namespace" "dev" {
  provider = kubernetes.dev
  metadata { name = "dosm-dev" }
}
resource "kubernetes_namespace" "prod" {
  provider = kubernetes.prod
  metadata { name = "dosm-prod" }
}

## Key Vault RBAC role assignments removed; using access policy instead for current user.

# Kubernetes namespaces via provider
## Kubernetes namespaces will be created after providers are reintroduced post-AKS creation.
