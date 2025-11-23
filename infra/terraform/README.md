# Terraform IaC for DOSM FAQ Chatbot

This Terraform configuration provisions a cost-aware dual AKS Azure architecture:

Resources:
- Resource Groups: `aks_dev_rg` (dev cluster), `aks_prod_rg` (prod cluster), `platform_rg` (shared services)
- ACR (Standard) shared across environments
- AKS: separate dev & prod clusters (autoscaling, monitoring addon)
- PostgreSQL Flexible Server (single server) with distinct dev/prod databases
- Storage Account with dev/prod artifact containers
- Key Vault + secrets (API keys, database URLs)
- Role assignments per cluster: ACR Pull, Key Vault Secrets User
- Kubernetes namespaces (dosm-dev on dev cluster, dosm-prod on prod cluster)

## Usage

1. Authenticate to Azure (CLI or env vars):
```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
```

2. Create a `terraform.tfvars` (DO NOT COMMIT SECRETS):
```hcl
postgres_admin_password = "<secure-password>"
api_key                 = "<single-api-key>"
```

3. Initialize and plan:
```bash
cd infra/terraform
terraform init
terraform plan -out plan.out
```

4. Apply:
```bash
terraform apply plan.out
```

5. Outputs:
- `acr_login_server`
- `aks_dev_name`
- `aks_prod_name`
- `postgres_fqdn`
- `key_vault_name`
- `storage_account_name`

## Variable Overrides (optional)
Override naming or sizes in `terraform.tfvars`:
```hcl
location              = "southeastasia"
aks_dev_node_size     = "Standard_B2s"      # burstable, fits quota
aks_dev_min_count     = 1
aks_dev_max_count     = 1                   # single node dev
aks_prod_node_size    = "Standard_B2s"
aks_prod_min_count    = 2                   # minimal HA
aks_prod_max_count    = 4                   # within Dv2/B-series quota
postgres_server_name  = "pg-dosm"
```

## Cleaning Up
```bash
terraform destroy
```

## Notes
- Dev cluster kept minimal (1 node) due to current VM family quota constraint; prod limited to 2–4 nodes.
- If Dv2 (or desired family) quota increases, raise `aks_dev_max_count` and `aks_prod_max_count` or move to Dsv5/D4as_v5 for higher performance.
- Single `api_key` is stored as Key Vault secret `API-KEY`; override per environment by injecting different value in CI or using separate Key Vault instances.
- Shared services (ACR, PostgreSQL, Storage, Key Vault) avoid duplication across environments.
- Secrets are stored directly to Key Vault; use CSI driver later for pod injection.
- PostgreSQL firewall rule allows Azure services (0.0.0.0); tighten for production.
- Change `kubernetes_version` and AKS node image as needed.
- For private networking add VNet, subnets, private endpoints (out of scope here).

## Next Enhancements
- Add Azure Monitor workspace + Diagnostic settings.
- Add Key Vault access via private endpoints.
- Integrate Key Vault CSI driver for secret mounting.
- Module decomposition for larger teams.
