# Deployment Guide: Azure Infrastructure for DOSM FAQ Chatbot

This guide details Azure resource provisioning and configuration for deploying the DOSM FAQ chatbot. Architecture uses **single AKS cluster with namespace separation** for cost optimization.

---

## Architecture Overview

- **Single AKS Cluster**: `dosm-aks` in `dosm-faq-chatbot-aks` resource group
- **Environment Separation**: Namespace-based (`dosm-dev`, `dosm-prod`)
- **Cost Optimization**: ~62% savings vs dual-cluster architecture
- **Shared Services**: PostgreSQL, Key Vault, ACR (environment-specific databases/secrets)

---

## Required Azure Resources

### 1. **Azure Kubernetes Service (AKS)**
- **Purpose**: Host API pods with HPA, run 2+ replicas for availability
- **Architecture**: Single cluster with namespace separation (`dosm-dev`, `dosm-prod`)
- **Resource Group**: `dosm-faq-chatbot-aks`
- **Cluster Name**: `dosm-aks`
- **Recommended SKU**: `Standard_D2s_v5` (2 vCPU, 8 GB) - 2-6 nodes with autoscaler
- **Features needed**:
  - Managed identity enabled
  - Azure Monitor Container Insights
  - Network policy (Azure CNI recommended)
  - Autoscaler (node pool and HPA)

### 2. **Azure Container Registry (ACR)**
- **Purpose**: Store Docker images
- **SKU**: Standard (geo-replication optional)
- **Name**: `dosm<unique-suffix>` (must be globally unique)
- **Resource Group**: `dosm-faq-chatbot-data`

### 3. **Azure Database for PostgreSQL Flexible Server**
- **Purpose**: Store inference logs and metrics
- **Databases**: `dosm_insights_dev`, `dosm_insights_prod`
- **SKU**: `Standard_B1ms` (1 vCore, 2 GB) - dev/prod shared
- **Features needed**:
  - Firewall rules (allow AKS subnet or Azure services)
  - SSL enforcement enabled
  - Backup retention 7+ days
- **Resource Group**: `dosm-faq-chatbot-data`

### 4. **Azure Storage Account**
- **Purpose**: Store training artifacts (embeddings, datasets, model checkpoints)
- **Containers**: `dosm-artifacts-dev`, `dosm-artifacts-prod`
- **SKU**: Standard LRS
- **Features needed**:
  - Blob storage enabled
  - Managed identity access for pods
- **Resource Group**: `dosm-faq-chatbot-data`

### 5. **Azure Key Vault**
- **Purpose**: Securely store API keys, database credentials
- **Secrets**: `API-KEY-DEV`, `API-KEY-PROD`, `DATABASE-URL-DEV`, `DATABASE-URL-PROD`
- **Features needed**:
  - RBAC enabled
  - Soft delete enabled
  - Managed identity access for AKS
- **Resource Group**: `dosm-faq-chatbot-data`

### 6. **Azure Monitor (Optional but Recommended)**
- **Purpose**: Centralized logging, metrics, alerts
- **Components**:
  - Log Analytics Workspace
  - Application Insights
  - Action Groups for alerting
- **Resource Group**: `dosm-faq-chatbot-data`

---

## Provisioning Steps

### Prerequisites
- Azure CLI installed (`az --version`)
- Helm CLI installed (`helm version`)
- kubectl installed (`kubectl version`)
- Azure subscription with appropriate permissions

### Step 1: Login and Set Subscription
```bash
az login
az account set --subscription "<Your-Subscription-ID>"
```

### Step 2: Define Variables
```bash
# Resource Groups
export RG_AKS="dosm-faq-chatbot-aks"
export RG_DATA="dosm-faq-chatbot-data"
export LOCATION="southeastasia"  # or your preferred region

# AKS
export AKS_NAME="dosm-aks"

# ACR
export ACR_NAME="dosm$(date +%s | tail -c 5)"  # unique suffix

# PostgreSQL
export POSTGRES_SERVER="pg-dosm"
export POSTGRES_USER="dosm_admin"
export POSTGRES_PASS="<GenerateSecurePassword>"  # Use Azure CLI or secure generator

# Storage
export STORAGE_ACCOUNT="dosmstorage$(date +%s | tail -c 5)"

# Key Vault
export KV_NAME="kv-dosm"
```

### Step 3: Create Resource Groups
```bash
az group create --name $RG_AKS --location $LOCATION
az group create --name $RG_DATA --location $LOCATION
```

### Step 4: Create Azure Container Registry (ACR)
```bash
az acr create \
  --resource-group $RG_DATA \
  --name $ACR_NAME \
  --sku Standard \
  --location $LOCATION

# Enable admin access (for initial testing)
az acr update --name $ACR_NAME --admin-enabled true

# Get ACR login server
export ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
echo "ACR Login Server: $ACR_LOGIN_SERVER"
```

### Step 5: Create AKS Cluster with Autoscaler
```bash
az aks create \
  --resource-group $RG_AKS \
  --name $AKS_NAME \
  --node-count 2 \
  --enable-managed-identity \
  --enable-cluster-autoscaler \
  --min-count 2 \
  --max-count 6 \
  --node-vm-size Standard_D2s_v5 \
  --network-plugin azure \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get AKS credentials
az aks get-credentials --resource-group $RG_AKS --name $AKS_NAME --overwrite-existing

# Verify cluster access
kubectl cluster-info
kubectl get nodes
```

### Step 6: Create Namespaces for Dev and Prod
```bash
kubectl create namespace dosm-dev
kubectl create namespace dosm-prod

# Set default context to dev (optional)
kubectl config set-context --current --namespace=dosm-dev
```

### Step 7: Create PostgreSQL Flexible Server with Separate Databases
```bash
az postgres flexible-server create \
  --resource-group $RG_DATA \
  --name $POSTGRES_SERVER \
  --location $LOCATION \
  --admin-user $POSTGRES_USER \
  --admin-password $POSTGRES_PASS \
  --sku-name Standard_B1ms \
  --storage-size 32 \
  --version 14 \
  --public-access 0.0.0.0

# Create databases for dev and prod
az postgres flexible-server db create \
  --resource-group $RG_DATA \
  --server-name $POSTGRES_SERVER \
  --database-name dosm_insights_dev

az postgres flexible-server db create \
  --resource-group $RG_DATA \
  --server-name $POSTGRES_SERVER \
  --database-name dosm_insights_prod

# Run schema migration (from sql/migrations/001_init_requests.sql)
export POSTGRES_HOST=$(az postgres flexible-server show \
  --resource-group $RG_DATA \
  --name $POSTGRES_SERVER \
  --query fullyQualifiedDomainName -o tsv)

# For dev database
psql "host=$POSTGRES_HOST port=5432 dbname=dosm_insights_dev user=$POSTGRES_USER password=$POSTGRES_PASS sslmode=require" \
  -f sql/migrations/001_init_requests.sql

# For prod database
psql "host=$POSTGRES_HOST port=5432 dbname=dosm_insights_prod user=$POSTGRES_USER password=$POSTGRES_PASS sslmode=require" \
  -f sql/migrations/001_init_requests.sql
```

### Step 8: Create Storage Account
```bash
az storage account create \
  --resource-group $RG_DATA \
  --name $STORAGE_ACCOUNT \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2

# Create containers for dev and prod
az storage container create \
  --name dosm-artifacts-dev \
  --account-name $STORAGE_ACCOUNT

az storage container create \
  --name dosm-artifacts-prod \
  --account-name $STORAGE_ACCOUNT
```

### Step 9: Create Azure Key Vault
```bash
az keyvault create \
  --resource-group $RG_DATA \
  --name $KV_NAME \
  --location $LOCATION \
  --enable-rbac-authorization true

# Store secrets (replace <values> with actual credentials)
az keyvault secret set --vault-name $KV_NAME --name "API-KEY-DEV" --value "<your-dev-api-key>"
az keyvault secret set --vault-name $KV_NAME --name "API-KEY-PROD" --value "<your-prod-api-key>"
az keyvault secret set --vault-name $KV_NAME --name "DATABASE-URL-DEV" \
  --value "postgresql://$POSTGRES_USER:$POSTGRES_PASS@$POSTGRES_HOST:5432/dosm_insights_dev"
az keyvault secret set --vault-name $KV_NAME --name "DATABASE-URL-PROD" \
  --value "postgresql://$POSTGRES_USER:$POSTGRES_PASS@$POSTGRES_HOST:5432/dosm_insights_prod"
```

---

## Connection Setups

### 1. **Connect AKS to ACR**
```bash
# Attach ACR to AKS (enables image pull without manual credentials)
az aks update \
  --resource-group $RG_AKS \
  --name $AKS_NAME \
  --attach-acr $ACR_NAME

# Verify connection
az aks check-acr \
  --resource-group $RG_AKS \
  --name $AKS_NAME \
  --acr $ACR_LOGIN_SERVER
```

### 2. **Grant AKS Managed Identity Access to Key Vault**
```bash
# Get AKS managed identity principal ID
export AKS_IDENTITY=$(az aks show \
  --resource-group $RG_AKS \
  --name $AKS_NAME \
  --query identityProfile.kubeletidentity.objectId -o tsv)

# Grant "Key Vault Secrets User" role
az role assignment create \
  --assignee $AKS_IDENTITY \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name $KV_NAME --query id -o tsv)
```

### 3. **Configure PostgreSQL Firewall Rules**
```bash
# Option A: Allow all Azure services (simpler but less secure)
az postgres flexible-server firewall-rule create \
  --resource-group $RG_DATA \
  --name $POSTGRES_SERVER \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Option B: Restrict to AKS subnet (more secure)
# Get AKS subnet ID
export AKS_SUBNET=$(az aks show \
  --resource-group $RG_AKS \
  --name $AKS_NAME \
  --query "agentPoolProfiles[0].vnetSubnetId" -o tsv)

# Add vnet rule (requires private endpoint or service endpoint)
# See Azure docs for detailed vnet integration steps
```

### 4. **Configure GitHub Actions Service Principal**
```bash
# Create service principal with contributor access
export APP_NAME="gh-actions-dosm-chatbot"
az ad sp create-for-rbac \
  --name $APP_NAME \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/$RG_AKS \
           /subscriptions/<subscription-id>/resourceGroups/$RG_DATA \
  --sdk-auth

# Output will contain credentials - save to GitHub secrets
# Required GitHub secrets:
# - AZURE_CREDENTIALS (full JSON output)
# - AZURE_CLIENT_ID
# - AZURE_TENANT_ID
# - AZURE_SUBSCRIPTION_ID
# - ACR_NAME
# - AKS_RG (dosm-faq-chatbot-aks)
# - AKS_NAME (dosm-aks)
```

---

## Helm Deployment

### Deploy to Dev Environment
```bash
# Ensure you're using the correct namespace
kubectl config set-context --current --namespace=dosm-dev

# Create Kubernetes secrets (alternative to Key Vault integration)
kubectl create secret generic dosm-api-secret \
  --from-literal=api-key="<dev-api-key>" \
  --namespace=dosm-dev

kubectl create secret generic dosm-db-secret \
  --from-literal=database-url="postgresql://$POSTGRES_USER:$POSTGRES_PASS@$POSTGRES_HOST:5432/dosm_insights_dev" \
  --namespace=dosm-dev

# Deploy with Helm
helm upgrade --install dosm-faq-chatbot ./deploy/helm \
  --namespace dosm-dev \
  --values ./deploy/helm/values-dev.yaml \
  --set image.repository=$ACR_LOGIN_SERVER/dosm-faq-chatbot \
  --set image.tag=latest \
  --wait
```

### Deploy to Prod Environment
```bash
# Switch to prod namespace
kubectl config set-context --current --namespace=dosm-prod

# Create Kubernetes secrets
kubectl create secret generic dosm-api-secret \
  --from-literal=api-key="<prod-api-key>" \
  --namespace=dosm-prod

kubectl create secret generic dosm-db-secret \
  --from-literal=database-url="postgresql://$POSTGRES_USER:$POSTGRES_PASS@$POSTGRES_HOST:5432/dosm_insights_prod" \
  --namespace=dosm-prod

# Deploy with Helm
helm upgrade --install dosm-faq-chatbot ./deploy/helm \
  --namespace dosm-prod \
  --values ./deploy/helm/values-prod.yaml \
  --set image.repository=$ACR_LOGIN_SERVER/dosm-faq-chatbot \
  --set image.tag=v1.0.0 \
  --wait
```

---

## Verification Steps

### Check Dev Deployment
```bash
kubectl get pods -n dosm-dev
kubectl get svc -n dosm-dev
kubectl get ingress -n dosm-dev
kubectl logs -l app=dosm-faq-chatbot -n dosm-dev --tail=50

# Test health endpoint
export DEV_INGRESS=$(kubectl get ingress dosm-faq-chatbot-ingress -n dosm-dev -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$DEV_INGRESS/health
```

### Check Prod Deployment
```bash
kubectl get pods -n dosm-prod
kubectl get svc -n dosm-prod
kubectl get ingress -n dosm-prod
kubectl logs -l app=dosm-faq-chatbot -n dosm-prod --tail=50

# Test health endpoint
export PROD_INGRESS=$(kubectl get ingress dosm-faq-chatbot-ingress -n dosm-prod -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$PROD_INGRESS/health
```

### Verify Database Connectivity
```bash
# Connect to dev database
psql "host=$POSTGRES_HOST port=5432 dbname=dosm_insights_dev user=$POSTGRES_USER password=$POSTGRES_PASS sslmode=require"

# Check inference_requests table (should exist from migration)
\dt
SELECT COUNT(*) FROM inference_requests;

# Connect to prod database
psql "host=$POSTGRES_HOST port=5432 dbname=dosm_insights_prod user=$POSTGRES_USER password=$POSTGRES_PASS sslmode=require"

# Check inference_requests table
\dt
SELECT COUNT(*) FROM inference_requests;
```

---

## Cost Estimates (Southeast Asia region)

| Resource | SKU/Configuration | Monthly Cost (USD) |
|----------|-------------------|-------------------|
| **AKS** | 2-6 nodes (Standard_D2s_v5, autoscale) | ~$140-$420 |
| **ACR** | Standard | ~$20 |
| **PostgreSQL** | Flexible Server (B1ms, 32GB storage) | ~$30 |
| **Storage Account** | Standard LRS (50GB) | ~$1 |
| **Key Vault** | Standard (10 secrets) | ~$0.30 |
| **Monitor** | Log Analytics (5GB/month) | ~$15 |
| **Total** | Single cluster with namespaces | **~$206-$486** |

**Cost Optimization vs Dual-Cluster Architecture:**
- **Dual-cluster**: ~$722/month (2 AKS clusters at $280 each, 2 PostgreSQL at $30 each, 2 Key Vaults)
- **Single-cluster**: ~$268/month (average autoscale, shared services)
- **Savings**: ~62% cost reduction

**Additional Cost Optimization Tips:**
- Enable AKS node pool autoscaler (scale down during off-hours)
- Use Azure Reserved Instances for predictable workloads (up to 72% discount)
- Implement aggressive HPA scaling policies (target CPU 70-80%)
- Use Spot VMs for non-production workloads (up to 90% discount)
- Configure budget alerts in Azure Cost Management

---

## Troubleshooting

### Pod CrashLoopBackOff
```bash
kubectl describe pod <pod-name> -n dosm-dev
kubectl logs <pod-name> -n dosm-dev --previous
```

Common causes:
- Missing secrets (`dosm-api-secret`, `dosm-db-secret`)
- Invalid DATABASE_URL format
- PostgreSQL firewall blocking AKS
- Image pull errors (ACR not attached)

### Cannot Pull Image from ACR
```bash
# Verify ACR attachment
az aks check-acr --resource-group $RG_AKS --name $AKS_NAME --acr $ACR_LOGIN_SERVER

# Re-attach if needed
az aks update --resource-group $RG_AKS --name $AKS_NAME --attach-acr $ACR_NAME
```

### Database Connection Timeout
```bash
# Check PostgreSQL firewall rules
az postgres flexible-server firewall-rule list \
  --resource-group $RG_DATA \
  --name $POSTGRES_SERVER

# Test connectivity from local machine
psql "host=$POSTGRES_HOST port=5432 dbname=dosm_insights_dev user=$POSTGRES_USER password=$POSTGRES_PASS sslmode=require"
```

### Ingress Not Assigning IP
```bash
# Check ingress controller logs
kubectl logs -n kube-system -l app.kubernetes.io/name=ingress-nginx

# Verify ingress resource
kubectl describe ingress dosm-faq-chatbot-ingress -n dosm-dev
```

---

## Next Steps

1. **CI/CD (GitHub Actions)**:
   - Workflow: `.github/workflows/deploy-dev.yml` triggers on `main` push.
   - Stages: test -> build & push -> helm upgrade.
   - Required GitHub Secrets:
     - `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
     - `ACR_NAME` (e.g. `dosmfaqchatbotacr1lw5a`)
     - `AKS_RG_DEV`, `AKS_NAME_DEV` (dev resource group & cluster name)
   - Image tag uses short SHA; model version set to `dosm-rag-<sha>`.
   - Extend similarly for prod (`AKS_RG_PROD`, `AKS_NAME_PROD`) in a separate workflow.
   - Add OIDC federated credential in Azure AD for GitHub repository (no static secrets).
   - Command override sample (manual):
     ```bash
     helm upgrade --install faq-chatbot-dev deploy/helm \
       --namespace dosm-dev -f deploy/helm/values-dev.yaml \
       --set image.repository=$ACR_LOGIN_SERVER/dosm-faq-chatbot \
       --set image.tag=$(git rev-parse --short HEAD) \
       --set env.MODEL_VERSION=dosm-rag-$(git rev-parse --short HEAD)
     ```
2. **Configure Monitoring**:
   - Set up Application Insights for distributed tracing
   - Configure log queries in Log Analytics
   - Create alert rules for error rates, latency, pod restarts

3. **Enable GitOps** (optional):
   - Install Flux or ArgoCD for declarative deployments
   - Store Helm values in separate Git repo
   - Automate dev → prod promotion

4. **Secure Ingress**:
   - Configure TLS certificates (Let's Encrypt or Azure-managed)
   - Enable WAF (Web Application Firewall)
   - Restrict ingress to specific IPs/VNets

5. **Backup Strategy**:
   - Configure PostgreSQL automated backups (7-35 days retention)
   - Export embeddings to Azure Storage Account regularly
   - Document disaster recovery procedures

6. **Performance Tuning**:
   - Load test with Locust/k6 to determine optimal replica count
   - Adjust HPA targets based on actual traffic patterns
   - Monitor RAG query latency and optimize vector search

---

## References

- [Azure AKS Best Practices](https://learn.microsoft.com/en-us/azure/aks/best-practices)
- [Azure PostgreSQL Flexible Server Docs](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/)
- [Helm Chart Best Practices](https://helm.sh/docs/chart_best_practices/)
- [GitHub Actions with Azure](https://docs.github.com/en/actions/deployment/deploying-to-your-cloud-provider/deploying-to-azure)
