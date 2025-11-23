# Database Secrets Setup Guide

## ✅ Completed: Database Migration

Both dev and prod databases now have pgvector enabled with the embeddings table:

- **Server**: `pg-dosm.postgres.database.azure.com`
- **Resource Group**: `dosm-faq-chatbot-data`
- **Dev Database**: `dosm-faq-chatbot-dev-postgres`
- **Prod Database**: `dosm-faq-chatbot-prod-postgres`
- **Admin User**: `dosm_admin`

**Migration Status**: ✅ Successfully ran `002_vector_store.sql` on both databases

## Required: Store DATABASE_URL in Azure Key Vault

### Option 1: Azure Portal (Recommended if RBAC permissions blocked)

1. Go to Azure Portal → Key Vault `kv-dosm`
2. Navigate to **Secrets** → **Generate/Import**
3. Add two secrets:

**Dev Database Secret:**
- Name: `dev-database-url`
- Value: `postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require`

**Prod Database Secret:**
- Name: `prod-database-url`
- Value: `postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-prod-postgres?sslmode=require`

### Option 2: Azure CLI (if you have Key Vault Secrets Officer role)

```bash
# Add dev database URL
az keyvault secret set \
  --vault-name kv-dosm \
  --name dev-database-url \
  --value "postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require"

# Add prod database URL
az keyvault secret set \
  --vault-name kv-dosm \
  --name prod-database-url \
  --value "postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-prod-postgres?sslmode=require"
```

## Kubernetes Secret Configuration

### Current Setup

Your Helm values already reference database secrets:

**values-dev.yaml:**
```yaml
env:
  DB:
    URL_SECRET: dev-db-url
    URL_KEY: DATABASE_URL
```

### Creating Kubernetes Secrets

You need to create Kubernetes secrets in your AKS clusters:

#### For Dev Cluster:

```bash
# Get AKS credentials
az aks get-credentials \
  --resource-group dosm-faq-chatbot-dev-rg \
  --name dosm-faq-chatbot-dev-aks

# Create namespace if not exists
kubectl create namespace dosm-dev --dry-run=client -o yaml | kubectl apply -f -

# Create secret
kubectl create secret generic dev-db-url \
  --from-literal=DATABASE_URL="postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require" \
  --namespace dosm-dev
```

#### For Prod Cluster:

```bash
# Get AKS credentials
az aks get-credentials \
  --resource-group dosm-faq-chatbot-prod-rg \
  --name dosm-faq-chatbot-prod-aks

# Create namespace if not exists
kubectl create namespace dosm-prod --dry-run=client -o yaml | kubectl apply -f -

# Create secret
kubectl create secret generic prod-db-url \
  --from-literal=DATABASE_URL="postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-prod-postgres?sslmode=require" \
  --namespace dosm-prod
```

### Alternative: Use Key Vault CSI Driver (Recommended for Production)

Your Helm chart already has Key Vault CSI templates. To use them:

1. Enable Key Vault CSI in values:
```yaml
keyVaultCSI:
  enabled: true
  tenantId: "09866460-551b-4cd5-8f73-e34f57be144b"
  vaultName: "kv-dosm"
  objects: |
    array:
      - objectName: dev-database-url  # or prod-database-url
        objectType: secret
        objectAlias: DATABASE_URL
```

2. Grant AKS managed identity access to Key Vault:
```bash
# Get AKS managed identity
AKS_IDENTITY=$(az aks show \
  --resource-group dosm-faq-chatbot-dev-rg \
  --name dosm-faq-chatbot-dev-aks \
  --query identityProfile.kubeletidentity.objectId -o tsv)

# Grant Key Vault Secrets User role
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee $AKS_IDENTITY \
  --scope $(az keyvault show --name kv-dosm --query id -o tsv)
```

## GitHub Actions Secrets

**DO NOT** add full database URLs to GitHub secrets if using Key Vault.

Instead, ensure your GitHub Actions service principal has:
1. **AcrPush** role on ACR (already configured)
2. **Contributor** role on AKS clusters (already configured)
3. **Key Vault Secrets User** role on `kv-dosm` (for reading secrets during deployment)

```bash
# Grant GitHub Actions SP access to Key Vault
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee bc0224aa-365e-40f4-bf19-5e8830865d09 \
  --scope $(az keyvault show --name kv-dosm --query id -o tsv)
```

## Firewall Rules

✅ Already configured:
- Local dev access: `60.53.32.26`
- Azure services: `0.0.0.0` (allows AKS pods)

## Next Steps

1. ✅ **Completed**: Run pgvector migration on dev/prod databases
2. **TODO**: Add `dev-database-url` and `prod-database-url` to Key Vault `kv-dosm`
3. **TODO**: Create Kubernetes secrets OR enable Key Vault CSI driver
4. **TODO**: Test ingestion Job: `helm upgrade --set ragIngest.enabled=true ...`
5. **TODO**: Verify `/predict` endpoint retrieves from PostgreSQL
6. **TODO**: Run evaluation harness to validate end-to-end functionality

## Testing Locally

To test the pgvector integration locally:

```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql://dosm_admin:Kusanagi@2105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require"

# Run ingestion
python -m train.train_rag_assets --input data/dosm_sample.csv

# Start app
uvicorn app.main:app --reload

# Test query
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the CPI for 2023?"}'
```

## Security Notes

- Database password is currently in plaintext - consider rotating and using stronger password
- Firewall rule allows specific IP - update if your IP changes
- SSL mode is required for all connections
- Key Vault should be the single source of truth for secrets
- Never commit DATABASE_URL to git (already in .gitignore)
