variable "location" {
	type    = string
	default = "southeastasia"
}
variable "project_name" {
	type    = string
	default = "dosm-faq-chatbot"
}
variable "aks_dev_rg_name" {
	type    = string
	default = "dosm-faq-chatbot-aks-dev"
}
variable "aks_prod_rg_name" {
	type    = string
	default = "dosm-faq-chatbot-aks-prod"
}
variable "platform_rg_name" {
	type    = string
	default = "dosm-faq-chatbot-data"
}
variable "aks_dev_name" {
	type    = string
	default = "dosm-aks-dev"
}
variable "aks_prod_name" {
	type    = string
	default = "dosm-aks-prod"
}
variable "acr_name_prefix" {
	type    = string
	default = "dosmacr"
}
variable "postgres_server_name" {
	type    = string
	default = "pg-dosm"
}
variable "postgres_admin_user" {
	type    = string
	default = "dosm_admin"
}
variable "postgres_admin_password" {
	type      = string
	sensitive = true
}
variable "postgres_storage_mb" {
	type    = number
	default = 32768
}
variable "postgres_version" {
	type    = string
	default = "14"
}
variable "db_dev_name" {
	type    = string
	default = "dosm_insights_dev"
}
variable "db_prod_name" {
	type    = string
	default = "dosm_insights_prod"
}
variable "storage_account_name_prefix" {
	type    = string
	default = "dosmstorage"
}
variable "key_vault_name" {
	type    = string
	default = "kv-dosm"
}
variable "api_key" {
	type      = string
	sensitive = true
	description = "Single API key used across environments (override in CI for prod if needed)."
}
variable "aks_dev_node_size" {
	type    = string
	# Standard_D2s_v3: 2 vCPU, 8GB RAM
	default = "Standard_D2s_v3"
}
variable "aks_dev_min_count" {
	type    = number
	# Keep single dev node (system + workloads) for cost/quota.
	default = 1
}
variable "aks_dev_max_count" {
	type    = number
	# Allow scaling to 2 nodes for high load periods
	default = 2
}
variable "aks_prod_node_size" {
	type    = string
	# Standard_E2s_v3: 2 vCPU, 16GB RAM - memory-optimized
	default = "Standard_E2s_v3"
}
variable "aks_prod_min_count" {
	type    = number
	# Start with 1 node (2 cores) keeping total cores at dev(2)+prod(2)=4.
	default = 1
}
variable "aks_prod_max_count" {
	type    = number
	# Allow scaling to 2 nodes for production high availability
	default = 2
}
variable "tags" {
	type    = map(string)
	default = {
		owner = "dosm"
		env   = "shared"
	}
}
