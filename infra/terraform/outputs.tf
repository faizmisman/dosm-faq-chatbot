output "acr_login_server" { value = azurerm_container_registry.acr.login_server }
output "aks_dev_name" { value = azurerm_kubernetes_cluster.aks_dev.name }
output "aks_prod_name" { value = azurerm_kubernetes_cluster.aks_prod.name }
output "postgres_fqdn" { value = azurerm_postgresql_flexible_server.pg.fqdn }
output "key_vault_name" { value = azurerm_key_vault.kv.name }
output "storage_account_name" { value = azurerm_storage_account.storage.name }
