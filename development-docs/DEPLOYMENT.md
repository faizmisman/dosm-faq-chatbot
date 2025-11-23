# Azure Deployment Guide – DOSM FAQ Chatbot

## Required Azure Resources

### 1. **Azure Kubernetes Service (AKS)**
- **Purpose**: Host API pods with HPA, run 1-2 replicas for availability
- **Recommended SKU**: `Standard_D2s_v5` (2 vCPU, 8 GB) for dev; `Standard_D4s_v5` for prod
- **Resource Requirements per pod**:
  - CPU: 250m request, 1000m limit
  - Memory: 512Mi request, 1Gi limit
  - Reason: Embedding model download (~100MB) + inference requires sufficient memory
- **Features needed**:
  - Managed identity enabled
  - Azure Monitor Container Insights
  - Network policy (Azure CNI recommended)
  - Autoscaler (node pool and HPA)

### 2. **Azure Container Registry (ACR)**
- **Purpose**: Store Docker images built by CI/CD
- **Recommended SKU**: Basic for dev; Standard or Premium for prod (geo-replication, webhooks)
- **Features**:
  - Admin user disabled (use managed identity)
  - Content trust for prod

### 3. **Azure Database for PostgreSQL – Flexible Server**
- **Purpose**: Store inference request logs, vector embeddings (pgvector), model metadata
- **Recommended SKU**: `Burstable_B1ms` (1 vCore, 2 GB) for dev; `GeneralPurpose_D2s_v3` for prod
- **Required Extensions**: 
  - `pgvector` (for vector similarity search)
  - `pg_stat_statements` (for query performance monitoring)
- **Features**:
  - High availability (zone-redundant) for prod
  - Automated backups (7-35 days retention)
  - Private endpoint or VNET integration recommended
  - Firewall rules configured for AKS egress IPs

### 4. **Azure Storage Account**
- **Purpose**: Store raw DOSM datasets, vector store snapshots, training artifacts
- **Recommended**: Standard LRS for dev; ZRS or GRS for prod
- **Containers**:
  - `dosm-raw`: raw CSV/Excel downloads
  - `dosm-artifacts`: trained embeddings, Chroma vector stores

### 5. **Azure Key Vault**
- **Purpose**: Securely store secrets (`API_KEY`, `DATABASE_URL`, LLM API keys)
- **Recommended SKU**: Standard
- **Access**: Managed identity from AKS (RBAC or access policies)
- **Optional**: Enable soft delete and purge protection for prod

### 6. **Managed Identity**
- **Purpose**: Secure, password-less access between services
- **Types**:
  - System-assigned for AKS
  - User-assigned for ACR pull, Key Vault access, Storage access

### 7. **Azure Monitor (Logs + Metrics)**
- **Purpose**: Centralized logging and alerting
- **Components**:
  - Log Analytics Workspace (container logs, Kusto queries)
  - Application Insights (optional for distributed tracing)
  - Managed Prometheus + Grafana (or self-hosted in AKS)

### 8. **Networking (Optional)**
- **Azure Virtual Network**: Private AKS cluster, service endpoints
- **Azure Front Door + WAF**: Public ingress with DDoS protection, rate limiting
- **Application Gateway**: Alternative to NGINX Ingress for advanced routing

---

## GitHub Actions CI/CD Setup

### Prerequisites
1. Azure App Registration (Service Principal) for OIDC authentication
2. GitHub repository secrets configured
3. Proper Azure RBAC permissions assigned

### Step 1: Create Azure App Registration
```bash
# Create app registration for GitHub OIDC
APP_NAME="github-oidc-dosm-insights"
az ad app create --display-name $APP_NAME

# Get the application (client) ID
APP_ID=$(az ad app list --display-name $APP_NAME --query "[0].appId" -o tsv)
echo "AZURE_CLIENT_ID: $APP_ID"

# Create service principal
az ad sp create --id $APP_ID

# Get service principal object ID
SP_OBJECT_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
```

### Step 2: Configure Federated Identity Credentials
```bash
# For main branch deployments
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-oidc-dosm-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:faizmisman/dosm-faq-chatbot:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# (Optional) For environment-based deployments
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-oidc-dosm-prod",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:faizmisman/dosm-faq-chatbot:environment:production",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### Step 3: Assign Azure RBAC Permissions
```bash
# Subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Grant Contributor on resource groups (or subscription)
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/dosm-faq-chatbot-dev-rg

az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/dosm-faq-chatbot-prod-rg

# Grant AcrPush on Container Registry
ACR_ID=$(az acr show --name dosmfaqchatbotacr1lw5a --query id -o tsv)
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role AcrPush \
  --scope $ACR_ID

# Grant Azure Kubernetes Service Cluster User Role
AKS_DEV_ID=$(az aks show -g dosm-faq-chatbot-dev-rg -n dosm-faq-chatbot-dev-aks --query id -o tsv)
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope $AKS_DEV_ID

AKS_PROD_ID=$(az aks show -g dosm-faq-chatbot-prod-rg -n dosm-faq-chatbot-prod-aks --query id -o tsv)
az role assignment create \
  --assignee $SP_OBJECT_ID \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope $AKS_PROD_ID
```

### Step 4: Configure GitHub Secrets
Add these secrets in GitHub repository settings (Settings → Secrets and variables → Actions):

```
AZURE_CLIENT_ID=<APP_ID from Step 1>
AZURE_TENANT_ID=<your tenant ID>
AZURE_SUBSCRIPTION_ID=<your subscription ID>
ACR_NAME=dosmfaqchatbotacr1lw5a
AKS_RG_DEV=dosm-faq-chatbot-dev-rg
AKS_NAME_DEV=dosm-faq-chatbot-dev-aks
AKS_RG_PROD=dosm-faq-chatbot-prod-rg
AKS_NAME_PROD=dosm-faq-chatbot-prod-aks
```

### Step 5: Verify Workflow
Push to `main` branch triggers `deploy-dev.yml`:
1. Runs tests
2. Builds Docker image with short SHA tag
3. Pushes to ACR
4. Deploys to dev AKS namespace via Helm (with 10-minute timeout)
5. Smoke tests `/health` endpoint

**Note**: First deployment may take 10+ minutes as pods download the embedding model (~100MB). Helm uses `--wait --timeout 10m` to accommodate this. Subsequent deployments are faster.

For prod deployment, create a version tag:
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Deployment Steps

### Phase 1: Provision Azure Resources

#### 1.1 Set variables
```bash
LOCATION="southeastasia"
RG_DEV="rg-dosm-dev"
RG_PROD="rg-dosm-prod"
AKS_DEV="aks-dosm-dev"
AKS_PROD="aks-dosm-prod"
ACR_NAME="acrdosminsights"  # globally unique, lowercase only
POSTGRES_DEV="pg-dosm-dev"
POSTGRES_PROD="pg-dosm-prod"
KV_DEV="kv-dosm-dev-$(openssl rand -hex 3)"
KV_PROD="kv-dosm-prod-$(openssl rand -hex 3)"
STORAGE_ACCOUNT="stdosmdata$(openssl rand -hex 3)"
```

#### 1.2 Create resource groups
```bash
az group create --name $RG_DEV --location $LOCATION
az group create --name $RG_PROD --location $LOCATION
```

#### 1.3 Create ACR
```bash
az acr create --resource-group $RG_DEV --name $ACR_NAME --sku Standard
```

#### 1.4 Create AKS clusters
**Dev:**
```bash
az aks create \
  --resource-group $RG_DEV \
  --name $AKS_DEV \
  --node-count 2 \
  --node-vm-size Standard_D2s_v5 \
  --enable-managed-identity \
  --attach-acr $ACR_NAME \
  --enable-addons monitoring \
  --generate-ssh-keys
```

**Prod:**
```bash
az aks create \
  --resource-group $RG_PROD \
  --name $AKS_PROD \
  --node-count 3 \
  --node-vm-size Standard_D4s_v5 \
  --enable-managed-identity \
  --attach-acr $ACR_NAME \
  --enable-addons monitoring \
  --enable-cluster-autoscaler \
  --min-count 2 \
  --max-count 10 \
  --generate-ssh-keys
```

#### 1.5 Create PostgreSQL databases
**Dev:**
```bash
az postgres flexible-server create \
  --resource-group $RG_DEV \
  --name $POSTGRES_DEV \
  --location $LOCATION \
  --admin-user dbadmin \
  --admin-password "YourSecurePassword!" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 15 \
  --storage-size 32

az postgres flexible-server db create \
  --resource-group $RG_DEV \
  --server-name $POSTGRES_DEV \
  --database-name dosm_insights
```

**Prod:** (add `--high-availability ZoneRedundant` for HA)

#### 1.6 Create Storage Account
```bash
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RG_DEV \
  --location $LOCATION \
  --sku Standard_LRS

az storage container create --name dosm-raw --account-name $STORAGE_ACCOUNT
az storage container create --name dosm-artifacts --account-name $STORAGE_ACCOUNT
```

#### 1.7 Create Key Vaults
```bash
az keyvault create \
  --name $KV_DEV \
  --resource-group $RG_DEV \
  --location $LOCATION \
  --enable-rbac-authorization

az keyvault create \
  --name $KV_PROD \
  --resource-group $RG_PROD \
  --location $LOCATION \
  --enable-rbac-authorization
```

---

### Phase 2: Configure Connections

#### 2.1 ACR ↔ AKS Integration
Already configured via `--attach-acr` flag. Verify:
```bash
az aks check-acr --resource-group $RG_DEV --name $AKS_DEV --acr $ACR_NAME.azurecr.io
```

#### 2.2 AKS → Key Vault (Managed Identity)
Get AKS identity:
```bash
AKS_IDENTITY=$(az aks show -g $RG_DEV -n $AKS_DEV --query identityProfile.kubeletidentity.clientId -o tsv)
```

Grant Key Vault Secrets User role:
```bash
KV_ID=$(az keyvault show -n $KV_DEV --query id -o tsv)
az role assignment create \
  --assignee $AKS_IDENTITY \
  --role "Key Vault Secrets User" \
  --scope $KV_ID
```

#### 2.3 AKS → PostgreSQL Firewall
Allow AKS egress IPs or use private endpoint:
```bash
# Get AKS outbound IP (for public postgres)
az aks show -g $RG_DEV -n $AKS_DEV --query networkProfile.loadBalancerProfile.effectiveOutboundIps -o table

# Add firewall rule (replace with actual IP)
az postgres flexible-server firewall-rule create \
  --resource-group $RG_DEV \
  --name $POSTGRES_DEV \
  --rule-name aks-dev-access \
  --start-ip-address <AKS_OUTBOUND_IP> \
  --end-ip-address <AKS_OUTBOUND_IP>
```

#### 2.4 GitHub Actions OIDC Federation
Create App Registration (one-time):
```bash
az ad app create --display-name "GitHub-DOSM-CICD"
APP_ID=$(az ad app list --display-name "GitHub-DOSM-CICD" --query [0].appId -o tsv)

# Create service principal
az ad sp create --id $APP_ID
SP_ID=$(az ad sp show --id $APP_ID --query id -o tsv)

# Add federated credential for GitHub Actions
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-main-branch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:faizmisman/dosm-faq-chatbot:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

Grant permissions to service principal:
```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Contributor on dev resource group
az role assignment create \
  --assignee $SP_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_DEV

# AcrPush on ACR
ACR_ID=$(az acr show -n $ACR_NAME --query id -o tsv)
az role assignment create \
  --assignee $SP_ID \
  --role AcrPush \
  --scope $ACR_ID
```

---

### Phase 3: GitHub Secrets Configuration

Add these secrets to your GitHub repository (`Settings` → `Secrets and variables` → `Actions`):

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `AZURE_CLIENT_ID` | `$APP_ID` | App registration client ID |
| `AZURE_TENANT_ID` | `$(az account show --query tenantId -o tsv)` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | `$SUBSCRIPTION_ID` | Subscription ID |
| `ACR_NAME` | `$ACR_NAME` | ACR name (no `.azurecr.io`) |
| `AKS_DEV_RG` | `$RG_DEV` | Dev resource group |
| `AKS_DEV_NAME` | `$AKS_DEV` | Dev AKS cluster name |
| `AKS_PROD_RG` | `$RG_PROD` | Prod resource group |
| `AKS_PROD_NAME` | `$AKS_PROD` | Prod AKS cluster name |

---

### Phase 4: Initial Deployment

#### 4.1 Store secrets in Key Vault
```bash
az keyvault secret set --vault-name $KV_DEV --name "API-KEY" --value "dev-secret-key"
az keyvault secret set --vault-name $KV_DEV --name "DATABASE-URL" \
  --value "postgresql://dbadmin:YourSecurePassword!@$POSTGRES_DEV.postgres.database.azure.com:5432/dosm_insights?sslmode=require"
```

#### 4.2 Update Helm values to reference Key Vault (optional: use CSI driver)
For now, Helm secret template uses inline values. For production, integrate Azure Key Vault CSI driver:
```bash
az aks enable-addons \
  --addons azure-keyvault-secrets-provider \
  --name $AKS_DEV \
  --resource-group $RG_DEV
```

#### 4.3 Deploy via Helm
Get AKS credentials:
```bash
az aks get-credentials --resource-group $RG_DEV --name $AKS_DEV
```

Run DB migration:
```bash
psql "postgresql://dbadmin:YourSecurePassword!@$POSTGRES_DEV.postgres.database.azure.com:5432/dosm_insights?sslmode=require" \
  -f sql/migrations/001_init_requests.sql
```

Deploy app:
```bash
helm upgrade --install dosm-insights ./deploy/helm \
  --set image.repository=$ACR_NAME.azurecr.io/dosm-insights-api \
  --set image.tag=latest \
  -f deploy/helm/values-dev.yaml
```

#### 4.4 Verify deployment
```bash
kubectl get pods
kubectl logs -l app.kubernetes.io/name=dosm-insights
kubectl get svc dosm-insights
```

Port-forward for local test:
```bash
kubectl port-forward svc/dosm-insights 8000:80
curl http://localhost:8000/health
```

---

### Phase 5: CI/CD Pipeline Execution

1. Push code to `main` branch → triggers `ci.yml` (test, build, push to ACR)
2. Merge to `main` → triggers `deploy-dev.yml` (Helm upgrade to dev AKS)
3. Manual trigger `promote-prod.yml` with image SHA for canary → promote

---

## Cost Estimates (Monthly, Southeast Asia)

| Resource | Dev SKU | Prod SKU | Est. Cost (Dev) | Est. Cost (Prod) |
|----------|---------|----------|-----------------|------------------|
| AKS (2 nodes) | D2s_v5 | D4s_v5 (3 nodes) | ~$150 | ~$400 |
| ACR | Standard | Standard | ~$5 | ~$5 |
| PostgreSQL | B1ms | D2s_v3 | ~$20 | ~$120 |
| Storage (100 GB) | LRS | ZRS | ~$2 | ~$3 |
| Key Vault | Standard | Standard | ~$1 | ~$1 |
| Log Analytics (5 GB) | - | - | ~$5 | ~$10 |
| **Total** | | | **~$183** | **~$539** |

---

## Next Steps

1. **Push code to GitHub** (resolve auth issue first)
2. **Provision Azure resources** using commands above
3. **Configure GitHub secrets**
4. **Trigger CI workflow** by pushing a commit
5. **Deploy to dev** via manual Helm or wait for auto-deploy
6. **Test endpoints** (`/health`, `/predict`)
7. **Set up monitoring** (Grafana dashboard import, alerts)
8. **Populate dataset** (upload CSV to Storage, set `DATASET_PATH` env)
9. **Promote to prod** using canary workflow

---

## Troubleshooting

### Helm Deployment Issues

**"UPGRADE FAILED: context deadline exceeded"**
- **Cause**: Helm waits for pods to be Ready. First pod start downloads embedding model (~26-30 seconds), which may exceed 5-minute timeout.
- **Solution**: Deploy-dev workflow now uses `--wait --timeout 10m`. For manual deployments:
  ```bash
  helm upgrade --install faq-chatbot-dev ./deploy/helm \
    -f deploy/helm/values-dev.yaml \
    --wait --timeout 10m
  ```
- **Note**: Helm may report "failed" but pods deploy successfully. Verify: `kubectl get pods -n dosm-dev`

### General Troubleshooting

- **ACR pull fails**: Check `az aks check-acr` and managed identity assignment
- **Key Vault access denied**: Verify RBAC role "Key Vault Secrets User" for AKS identity
- **Postgres connection refused**: Check firewall rules, verify connection string, ensure password is URL-encoded
- **GitHub Actions 403**: Ensure federated credential subject matches repo path exactly
- **Pod CrashLoopBackOff**: Check logs (`kubectl logs`), verify secrets exist, ensure DATABASE_URL password uses URL encoding (`@` → `%40`)

---

## Security Best Practices

- Never commit `.env` or secrets to git (`.gitignore` enforced)
- Use managed identities instead of connection strings where possible
- Enable private endpoints for Postgres and Storage in production
- Implement network policies in AKS to restrict pod-to-pod traffic
- Enable Azure Defender for containers and Key Vault
- Rotate API keys quarterly
- Use Azure Front Door WAF for public-facing endpoints
